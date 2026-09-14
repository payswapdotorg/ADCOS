"use client";

/**
 * QuickstartSteps — the nine step BODIES of the guided Quickstart
 * journey (the frozen V2 design §6; plan Task 5).
 *
 * The DEC-0128 program, Tasks 4-5 wave, Task 5 of the frozen plan. Each
 * step is a full-height guided screen carrying: a title, a short
 * explanation (curated product language, like the W1 docs prose), the
 * REAL object/API content where the step has one, and the W1 contextual
 * education. Sources are strict:
 *
 * - the demo document arrives ONLY through the typed client's
 *   `demoContractFulfillment` (the same call the V1 DemoCard makes) —
 *   the step bodies never fetch and never invent objects;
 * - the intent example is the coverage registry's OWN `intent_create`
 *   example body (verbatim); the field explanations are the W1
 *   operation-education registry's own `fieldExplanations`;
 * - every concept explanation renders through the W1 learning
 *   primitives (ConceptExplainer / ConceptLink / ObjectEducation /
 *   NextSteps) — no education string is re-authored here;
 * - honesty (§17): the SOFTWARE evidence class is shown through
 *   EvidenceBadge, physical/network evidence is stated as
 *   NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT (the V1 legend vocabulary), the
 *   demonstration is labeled deterministic, and the connect step offers
 *   the REAL connect dialog — no fake login.
 */

import { useState } from "react";
import Link from "next/link";
import { useSession } from "@/lib/session";
import type { DemoDocument } from "@/lib/api/types";
import { coverageByOperation } from "@/lib/api/coverage";
import { getConcept, getOperationEducation, getGuide } from "@/lib/education";
import type { LearningLink } from "@/lib/education";
import {
  ConceptExplainer,
  ConceptLink,
  NextSteps,
  ObjectEducation,
} from "@/features/learning";
import {
  DEMO_DETERMINISM_NOTE,
  registerDemoRun,
  type DemoDocumentView,
} from "@/features/fulfillment";
import { NOT_ACHIEVABLE_BY_THIS_DEPLOYMENT } from "@/features/evidence";
import { ConnectDialog } from "@/components/shell/connect-dialog";
import {
  ApiRequestPanel,
  ErrorState,
  EvidenceBadge,
  JsonViewer,
} from "@/components/ui";
import type { ObjectField } from "@/lib/objects";
import { ObjectFieldGrid, ObjectSection } from "@/features/eligibility";

/* ------------------------------------------------------------------ *
 * Shared step plumbing
 * ------------------------------------------------------------------ */

/** Stable test id for the whole step body region. */
export const QUICKSTART_STEP_TEST_ID = "quickstart-step";

/** Stable test id for the honest document-unavailable state. */
export const QUICKSTART_DOC_MISSING_TEST_ID = "quickstart-doc-missing";

/** Stable test id for the run-failure state (step 6). */
export const QUICKSTART_RUN_ERROR_TEST_ID = "quickstart-run-error";

/** What every document-backed step body receives. */
export interface QuickstartDocProps {
  doc: DemoDocument | null;
  view: DemoDocumentView | null;
  /** The journey's demonstration-read error, when the read failed. */
  readError: unknown;
  /** Re-run the journey's demonstration read (ErrorState retry). */
  onRetryRead: () => void;
}

/** The step's title + short explanation block. */
export function StepIntro({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <p className="max-w-3xl text-sm leading-relaxed text-ink-muted">
        {children}
      </p>
    </div>
  );
}

/** Mono field value (the V1 object-surface convention). */
function Mono({ children }: { children: React.ReactNode }) {
  return <span className="break-all font-mono text-xs text-ink">{children}</span>;
}

/**
 * The honest document-required guard: a document-backed step never
 * renders fabricated content — while the read is in flight it shows the
 * loading state, and when the read failed it shows the canonical
 * ErrorState carrying the REAL read error with the retry affordance.
 */
export function DocumentRequired({
  doc,
  readError,
  onRetryRead,
  children,
}: QuickstartDocProps & { children: React.ReactNode }) {
  if (!doc) {
    if (readError !== null && readError !== undefined) {
      return (
        <div
          data-testid={QUICKSTART_DOC_MISSING_TEST_ID}
          className="rounded-md border border-line bg-surface"
        >
          <ErrorState error={readError} onRetry={onRetryRead} />
        </div>
      );
    }
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        {[0, 1].map((index) => (
          <div
            key={index}
            className="h-24 animate-pulse rounded-md border border-line bg-surface"
          />
        ))}
      </div>
    );
  }
  return <>{children}</>;
}

/* ------------------------------------------------------------------ *
 * Step 1 — Connect or enter the demo context
 * ------------------------------------------------------------------ */

export function ConnectStep() {
  const { status, application } = useSession();
  const [dialogOpen, setDialogOpen] = useState(false);
  const connected = status === "connected";

  return (
    <div className="flex flex-col gap-4">
      <StepIntro title="Connect or enter the demo context">
        Every journey needs a context. Connect an application credential —
        or continue in the deterministic demonstration context, which is
        the supported unauthenticated platform demo. Both are honest
        starting points; nothing below requires a login.
      </StepIntro>

      <div className="grid gap-3 sm:grid-cols-2">
        <ObjectSection
          title="Connect an application"
          description="The real connect flow — validated against GET /api/2.0/application, the credential held in memory only."
        >
          {connected ? (
            <div className="flex flex-col gap-2">
              <p className="text-sm leading-relaxed text-ink-muted">
                This session is connected:
              </p>
              <dl className="grid grid-cols-[minmax(9rem,auto)_1fr] items-baseline gap-x-3 gap-y-1.5">
                <dt className="font-mono text-2xs text-ink-faint">
                  application_name
                </dt>
                <dd>
                  <Mono>{application?.application_name ?? "—"}</Mono>
                </dd>
                <dt className="font-mono text-2xs text-ink-faint">
                  environment
                </dt>
                <dd>
                  <Mono>{application?.environment ?? "—"}</Mono>
                </dd>
                <dt className="font-mono text-2xs text-ink-faint">
                  capabilities
                </dt>
                <dd className="text-xs text-ink-muted">
                  {(application?.capabilities ?? []).join(", ") || "—"}
                </dd>
              </dl>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={() => setDialogOpen(true)}
                className="inline-flex min-h-11 w-fit items-center rounded-md bg-accent px-4 text-sm font-medium text-accent-ink transition-colors hover:bg-accent-strong"
              >
                Connect application
              </button>
              <p className="text-xs leading-relaxed text-ink-faint">
                A reload clears the session by design — the credential is
                never persisted to browser storage.
              </p>
            </div>
          )}
        </ObjectSection>

        <ObjectSection
          title="…or the deterministic demo context"
          description="The unauthenticated platform demonstration this deployment exposes — no credential, no fake login."
        >
          <p className="text-sm leading-relaxed text-ink-muted">
            The objects in the next steps come from{" "}
            <span className="font-mono">GET /demo/contract-fulfillment</span>{" "}
            — the deterministic full-chain demonstration document. It is a
            demonstration, not production telemetry: identical instant →
            identical document, SOFTWARE evidence class only.
          </p>
          <p className="text-xs leading-relaxed text-ink-faint">
            Continue below either way — the journey works end to end in
            the demo context.
          </p>
        </ObjectSection>
      </div>

      <ConnectDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Step 2 — Describe a connectivity requirement
 * ------------------------------------------------------------------ */

export function RequirementStep() {
  // the REAL intent example — the coverage registry's own example body
  const intentExample = coverageByOperation("intent_create")?.example;
  // the REAL field explanations — the W1 operation-education registry
  const fieldExplanations =
    getOperationEducation("intent_create")?.fieldExplanations ?? [];

  return (
    <div className="flex flex-col gap-4">
      <StepIntro title="Describe a connectivity requirement">
        You don&apos;t configure networks — you describe the connectivity
        your application needs, and it becomes a durable contract. This is
        the demonstration&apos;s requirement in human terms; the canonical
        body below is the coverage registry&apos;s real{" "}
        <span className="font-mono">intent_create</span> example.
      </StepIntro>

      <div className="rounded-md border border-line bg-surface px-4 py-3.5">
        <h3 className="text-sm font-semibold text-ink">
          The requirement, in human terms
        </h3>
        <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-ink-muted">
          Keep a device&apos;s connectivity alive for one month — held to a{" "}
          <span className="font-mono text-xs text-ink">100 ms</span> latency
          bound and a{" "}
          <span className="font-mono text-xs text-ink">1000 bps</span>{" "}
          throughput floor — terminable when the principal asks or the
          window expires.
        </p>
        <p className="mt-2 text-xs leading-relaxed text-ink-faint">
          A reading of the canonical example below (its hard constraints
          and validity), not a new requirement: hard constraints are
          immutable once recorded, so describe them carefully.
        </p>
        <div className="mt-2">
          <ConceptLink id="connectivity-contract">
            What is a connectivity contract?
          </ConceptLink>
        </div>
      </div>

      <ObjectSection
        title="The canonical intent body — intent_create"
        description="The coverage registry's own example request body, verbatim: the material POST /api/2.0/intents carries."
      >
        {fieldExplanations.length > 0 ? (
          <dl className="flex flex-col gap-2">
            {fieldExplanations.map((field) => (
              <div
                key={field.field}
                className="grid grid-cols-[minmax(11rem,auto)_1fr] gap-x-3"
              >
                <dt className="break-all font-mono text-2xs text-ink-faint">
                  {field.field}
                </dt>
                <dd className="text-xs leading-relaxed text-ink-muted">
                  {field.explanation}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-sm text-ink-faint">
            no field explanations are recorded — nothing is invented
          </p>
        )}
        {intentExample ? (
          <JsonViewer
            value={intentExample}
            name="intent_create example"
            defaultExpandedDepth={3}
          />
        ) : (
          <p className="text-sm text-ink-faint">
            no example body is recorded for intent_create — nothing is
            invented
          </p>
        )}
      </ObjectSection>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Step 3 — Review the canonical contract representation
 * ------------------------------------------------------------------ */

export function ContractStep({
  doc,
  view,
  readError,
  onRetryRead,
}: QuickstartDocProps) {
  const concept = getConcept("connectivity-contract");
  const lifecyclePosition =
    getOperationEducation("intent_create")?.lifecyclePosition;

  // the raw contract record's requirement references (honest member
  // reads — the parsed view does not carry them, the raw record does)
  const requirements = doc
    ? Array.isArray(doc.contract.requirements)
      ? doc.contract.requirements
          .map((ref) =>
            typeof ref === "object" &&
            ref !== null &&
            "value" in ref &&
            typeof (ref as { value?: unknown }).value === "string"
              ? (ref as { value: string }).value
              : null,
          )
          .filter((value): value is string => value !== null)
      : []
    : [];

  return (
    <div className="flex flex-col gap-4">
      <StepIntro title="Review the canonical contract representation">
        The recorded requirement IS the contract — the sole durable
        authority, rendered here exactly as the demonstration document
        carries it.
      </StepIntro>

      <DocumentRequired doc={doc} view={view} readError={readError} onRetryRead={onRetryRead}>
        {doc && view ? (
          <ObjectEducation
            title="Connectivity contract"
            intro={
              concept
                ? concept.summary
                : "The canonical contract record, rendered verbatim below."
            }
            lifecyclePosition={lifecyclePosition}
            whatUserRequested={
              <span className="flex flex-col gap-1">
                <span>
                  {requirements.length} requirement reference
                  {requirements.length === 1 ? "" : "s"} · hard
                  constraints:{" "}
                  {view.contract.hard_constraints
                    .map(
                      (constraint) =>
                        `${constraint.kind} (${Object.entries(constraint.params)
                          .map(([key, value]) => `${key}=${String(value)}`)
                          .join(", ")})`,
                    )
                    .join(" · ") || "none"}
                </span>
                <span>
                  validity:{" "}
                  {view.contract.validity
                    ? `${view.contract.validity.not_before} → ${view.contract.validity.not_after}`
                    : "—"}
                </span>
                {requirements.length > 0 ? (
                  <span className="font-mono">{requirements.join(", ")}</span>
                ) : null}
              </span>
            }
            whyItMatters={concept?.whyItMatters}
            conceptId="connectivity-contract"
            headingLevel="h3"
          >
            <ObjectFieldGrid
              columns={2}
              fields={[
                {
                  label: "state",
                  value: <Mono>{view.contract.state}</Mono>,
                },
                {
                  label: "contract_id",
                  value: <Mono>{view.contract.contract_id}</Mono>,
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
                {
                  label: "accepted_offers",
                  value: (
                    <Mono>
                      {view.contract.accepted_offers
                        .map((offer) => offer.value)
                        .join(", ") || "none"}
                    </Mono>
                  ),
                },
              ]}
            />
            <JsonViewer
              value={doc.contract}
              name="contract"
              defaultExpandedDepth={1}
            />
          </ObjectEducation>
        ) : null}
      </DocumentRequired>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Step 4 — Explain eligibility and provider/policy reasoning
 * ------------------------------------------------------------------ */

export function EligibilityStep({
  doc,
  view,
  readError,
  onRetryRead,
}: QuickstartDocProps) {
  return (
    <div className="flex flex-col gap-4">
      <StepIntro title="Explain eligibility and provider/policy reasoning">
        Why is the flow state what it is? This deployment answers through
        the boundary trace the demonstration document carries — the real
        capability statements of how the canonical lifecycle was driven
        (intent → offer → activation) — and, per contract, the lifecycle
        observation. No provider eligibility list exists on the boundary;
        none is invented here.
      </StepIntro>

      <ConceptExplainer id="eligibility" mode="inline" />

      <DocumentRequired doc={doc} view={view} readError={readError} onRetryRead={onRetryRead}>
        {doc ? (
          <ObjectSection
            title="The boundary trace — the capability statements this deployment exposes"
            description="DemoDocument.boundary, verbatim: the requests the boundary leg drove through the durable idempotency discipline."
          >
            <div className="w-full overflow-x-auto rounded-md border border-line bg-surface">
              <table
                aria-label="The demonstration's boundary trace"
                className="w-full border-separate border-spacing-0 text-sm"
              >
                <thead>
                  <tr>
                    {["method", "route", "status", "request_id"].map((column) => (
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
                  {doc.boundary.map((entry) => (
                    <tr
                      key={entry.request_id}
                      className="border-b border-line last:border-b-0"
                    >
                      <td className="px-3 py-1.5 font-mono text-xs text-ink">
                        {entry.method}
                      </td>
                      <td className="break-all px-3 py-1.5 font-mono text-xs text-ink">
                        {entry.route}
                      </td>
                      <td className="px-3 py-1.5 font-mono text-xs text-ink">
                        {String(entry.status)}
                      </td>
                      <td
                        className="break-all px-3 py-1.5 font-mono text-2xs text-ink-faint"
                        title={entry.request_id}
                      >
                        {entry.request_id}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs leading-relaxed text-ink-faint">
              Provider eligibility decisions as a list are not exposed by
              this deployment — what is exposed is this trace and, per
              contract, the lifecycle observation (intent_lifecycle).
            </p>
          </ObjectSection>
        ) : null}
      </DocumentRequired>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Step 5 — Show the generated fulfillment plan
 * ------------------------------------------------------------------ */

export function PlanStep({
  doc,
  view,
  readError,
  onRetryRead,
}: QuickstartDocProps) {
  const concept = getConcept("execution-plan");

  const planFields: ObjectField[] = [
    {
      label: "plan_id",
      value: view ? <Mono>{view.plan.plan_id}</Mono> : null,
    },
    {
      label: "contract_id",
      value: view ? <Mono>{view.plan.contract_id}</Mono> : null,
    },
    {
      label: "constraint_fingerprint",
      value: view ? <Mono>{view.plan.constraint_fingerprint}</Mono> : null,
      hint: "Binds the plan to the contract's hard constraints — the plan-verification gate re-verifies that every candidate plan preserves them.",
    },
    {
      label: "segments",
      value: view ? (
        <Mono>
          {view.plan.segments
            .map(
              (segment) =>
                `${segment.role} · ${segment.operations.join(" → ")}`,
            )
            .join(", ") || "none"}
        </Mono>
      ) : null,
    },
    {
      label: "provenance",
      value: view?.plan.provenance ? (
        <Mono>
          issuer {view.plan.provenance.issuer}
          {view.plan.provenance.decision_refs.length > 0
            ? ` · decision_refs ${view.plan.provenance.decision_refs.join(", ")}`
            : ""}
        </Mono>
      ) : null,
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <StepIntro title="Show the generated fulfillment plan">
        ADCOS composes provider capabilities into an execution plan over
        the contract&apos;s canonical hard constraints — never weakening
        them. This is the demonstration&apos;s real plan.
      </StepIntro>

      <DocumentRequired doc={doc} view={view} readError={readError} onRetryRead={onRetryRead}>
        {doc && view ? (
          <ObjectEducation
            title="Execution plan"
            intro={
              concept
                ? concept.summary
                : "The canonical plan record, rendered verbatim below."
            }
            whyItMatters={concept?.whyItMatters}
            conceptId="execution-plan"
            headingLevel="h3"
          >
            <ObjectFieldGrid columns={1} fields={planFields} />
            <JsonViewer value={doc.plan} name="plan" defaultExpandedDepth={1} />
          </ObjectEducation>
        ) : null}
      </DocumentRequired>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Step 6 — Run or observe fulfillment
 * ------------------------------------------------------------------ */

export function RunStep({
  doc,
  view,
  readError,
  onRetryRead,
}: QuickstartDocProps) {
  return (
    <div className="flex flex-col gap-4">
      <StepIntro title="Run or observe fulfillment">
        The plan executes through reserve → activate → measure → release.
        You already observed the pre-fetched document; now run the same
        demonstration the way the console runs it — a real POST through
        the typed client.
      </StepIntro>

      <DocumentRequired doc={doc} view={view} readError={readError} onRetryRead={onRetryRead}>
        {doc ? <RunFulfillment doc={doc} view={view} /> : null}
      </DocumentRequired>
    </div>
  );
}

function RunFulfillment({
  doc,
  view,
}: {
  doc: DemoDocument;
  view: DemoDocumentView | null;
}) {
  const { client } = useSession();
  const [running, setRunning] = useState(false);
  const [ranDoc, setRanDoc] = useState<DemoDocument | null>(null);
  const [error, setError] = useState<unknown>(null);

  const finalSegmentState =
    view && view.execution.segment_states.length > 0
      ? view.execution.segment_states[view.execution.segment_states.length - 1]
      : null;

  async function run() {
    if (running) return;
    setRunning(true);
    setError(null);
    try {
      const result = await client.demoContractFulfillment(doc.instant);
      setRanDoc(result);
      registerDemoRun({
        instant: result.instant,
        ranAt: new Date().toISOString(),
        contractId: String(result.contract.contract_id ?? ""),
        planId: String(result.plan.plan_id ?? ""),
      });
    } catch (caught) {
      setRanDoc(null);
      setError(caught);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <ObjectSection
        title="Observed so far (the GET document)"
        description="What steps 3-5 rendered: the deterministic chain at this instant."
      >
        <ObjectFieldGrid
          columns={2}
          fields={[
            { label: "instant", value: <Mono>{doc.instant}</Mono> },
            { label: "mode", value: <Mono>{doc.mode}</Mono> },
            { label: "environment", value: <Mono>{doc.environment}</Mono> },
            {
              label: "evidence_class",
              value: <EvidenceBadge evidenceClass={doc.evidence_class} />,
            },
            {
              label: "final segment state",
              value: <Mono>{finalSegmentState ?? "—"}</Mono>,
            },
            {
              label: "evidence records",
              value: <Mono>{doc.evidence.length}</Mono>,
            },
          ]}
        />
      </ObjectSection>

      <ObjectSection
        title="Run it now"
        description="POST /demo/contract-fulfillment with the observed instant — a genuine replay through the boundary's own idempotency ledger."
      >
        <div className="flex flex-col gap-3">
          <button
            type="button"
            onClick={run}
            disabled={running}
            className="inline-flex min-h-11 w-fit items-center rounded-md bg-accent px-4 text-sm font-medium text-accent-ink transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
          >
            {running ? "running…" : "Run the demonstration"}
          </button>
          <p className="text-xs leading-relaxed text-ink-faint">
            {DEMO_DETERMINISM_NOTE} The run registers in this session&apos;s
            demonstration-run registry so Fulfillment lists it.
          </p>

          {error ? (
            <div
              data-testid={QUICKSTART_RUN_ERROR_TEST_ID}
              className="rounded-md border border-line bg-surface"
            >
              <ErrorState error={error} onRetry={run} />
            </div>
          ) : null}

          {ranDoc ? (
            <div
              data-testid="quickstart-run-summary"
              className="flex flex-col gap-2 rounded-md border border-line bg-raised px-3 py-2.5"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-ink">
                  Ran at instant
                </span>
                <Mono>{ranDoc.instant}</Mono>
                <EvidenceBadge evidenceClass={ranDoc.evidence_class} />
              </div>
              <ObjectFieldGrid
                columns={2}
                fields={[
                  { label: "mode", value: <Mono>{ranDoc.mode}</Mono> },
                  { label: "environment", value: <Mono>{ranDoc.environment}</Mono> },
                  {
                    label: "contract",
                    value: (
                      <Link
                        href={`/connectivity/contracts/${String(ranDoc.contract.contract_id)}`}
                        className="break-all font-mono text-xs text-accent transition-colors hover:text-ink"
                      >
                        {String(ranDoc.contract.contract_id)}
                      </Link>
                    ),
                  },
                  {
                    label: "plan",
                    value: <Mono>{String(ranDoc.plan.plan_id)}</Mono>,
                  },
                  {
                    label: "evidence records",
                    value: <Mono>{ranDoc.evidence.length}</Mono>,
                  },
                ]}
              />
            </div>
          ) : null}
        </div>
      </ObjectSection>

      <p className="rounded-md border border-dashed border-line bg-raised px-3 py-2 text-xs leading-relaxed text-ink-muted">
        <span className="font-medium text-ink">Evidence-class honesty.</span>{" "}
        The demonstration carries{" "}
        <EvidenceBadge evidenceClass="SOFTWARE" size="sm" /> evidence only —
        physical/network evidence is{" "}
        <span className="font-mono text-xs text-ink">
          {NOT_ACHIEVABLE_BY_THIS_DEPLOYMENT}
        </span>
        , and no UI state can turn software-side evidence into a physical
        PASS.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Step 7 — Inspect evidence and assurance
 * ------------------------------------------------------------------ */

export function EvidenceStep({
  doc,
  view,
  readError,
  onRetryRead,
}: QuickstartDocProps) {

  return (
    <div className="flex flex-col gap-4">
      <StepIntro title="Inspect evidence and assurance">
        What the system claims is backed by records you can inspect — each
        with a producer, an instant, a subject and an evidence class.
        Assurance obligations ride the contract as referenced material.
      </StepIntro>

      <DocumentRequired doc={doc} view={view} readError={readError} onRetryRead={onRetryRead}>
        {doc && view ? (
          <div className="flex flex-col gap-4">
            <ObjectSection
              title={`Evidence records (${doc.evidence.length})`}
              description="DemoDocument.evidence, verbatim — every record carries the document's own evidence class."
            >
              {view.evidence.length === 0 ? (
                <p className="text-sm text-ink-faint">
                  no evidence records in the document
                </p>
              ) : (
                <div className="flex flex-col gap-3">
                  {view.evidence.map((record) => (
                    <article
                      key={record.record_id}
                      data-testid="quickstart-evidence-record"
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
                        <EvidenceBadge
                          evidenceClass={doc.evidence_class}
                          size="sm"
                        />
                      </div>
                      <dl className="mt-2 grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-3 gap-y-1.5">
                        <dt className="font-mono text-2xs text-ink-faint">
                          producer
                        </dt>
                        <dd className="break-all font-mono text-xs text-ink">
                          {record.producer}
                        </dd>
                        <dt className="font-mono text-2xs text-ink-faint">
                          instant
                        </dt>
                        <dd className="font-mono text-xs text-ink">
                          {record.instant}
                        </dd>
                        {record.record_type === "observation" ? (
                          <>
                            <dt className="font-mono text-2xs text-ink-faint">
                              metric
                            </dt>
                            <dd className="font-mono text-xs text-ink">
                              {record.metric ?? "—"}
                            </dd>
                            <dt className="font-mono text-2xs text-ink-faint">
                              value
                            </dt>
                            <dd className="font-mono text-xs text-ink">
                              {String(record.value ?? "—")}
                            </dd>
                          </>
                        ) : (
                          <>
                            <dt className="font-mono text-2xs text-ink-faint">
                              attestation_kind
                            </dt>
                            <dd className="font-mono text-xs text-ink">
                              {record.attestation_kind ?? "—"}
                            </dd>
                            <dt className="font-mono text-2xs text-ink-faint">
                              attested_value
                            </dt>
                            <dd className="font-mono text-xs text-ink">
                              {String(record.attested_value ?? "—")}
                            </dd>
                          </>
                        )}
                        <dt className="font-mono text-2xs text-ink-faint">
                          confidence_basis_points
                        </dt>
                        <dd className="font-mono text-xs text-ink">
                          {record.confidence_basis_points ?? "—"}
                        </dd>
                      </dl>
                    </article>
                  ))}
                </div>
              )}
              <p className="text-xs leading-relaxed text-ink-faint">
                SOFTWARE evidence stays visibly software-side (the dashed
                badge); physical/network evidence is{" "}
                <span className="font-mono">
                  {NOT_ACHIEVABLE_BY_THIS_DEPLOYMENT}
                </span>
                .
              </p>
            </ObjectSection>

            <ObjectSection
              title="Assurance obligations"
              description="Referenced on the contract — the console shows them verbatim with provenance, never evaluates them."
            >
              {view.contract.assurance_obligations.length === 0 ? (
                <p className="text-sm text-ink-faint">
                  no assurance obligations referenced
                </p>
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {view.contract.assurance_obligations.map((obligation) => (
                    <li
                      key={obligation.value}
                      className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5"
                    >
                      <span className="rounded border border-line-strong px-1 font-mono text-2xs text-ink-muted">
                        {obligation.ref_kind}
                      </span>
                      <span className="break-all font-mono text-xs text-ink">
                        {obligation.value}
                      </span>
                      {obligation.provenance ? (
                        <span className="break-all font-mono text-2xs text-ink-faint">
                          issuer {obligation.provenance.issuer}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-1">
                <ConceptExplainer id="assurance" mode="inline" />
              </div>
            </ObjectSection>
          </div>
        ) : null}
      </DocumentRequired>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Step 8 — Reproduce an operation through the API Explorer
 * ------------------------------------------------------------------ */

export function ApiReproduceStep({
  doc,
  view,
  readError,
  onRetryRead,
}: QuickstartDocProps) {
  return (
    <div className="flex flex-col gap-4">
      <StepIntro title="Reproduce an operation through the API Explorer">
        Everything you just saw is one HTTP request. This is the curl for
        the demonstration POST — the same request the Run step made — and
        the Explorer will run it for real.
      </StepIntro>

      <DocumentRequired doc={doc} view={view} readError={readError} onRetryRead={onRetryRead}>
        {doc ? (
          <ObjectSection
            title="Reproduce the demonstration run"
            description="The masked-curl convention every console surface uses — a platform route, so there are no credential headers to mask."
          >
            <ApiRequestPanel
              method="POST"
              path="/demo/contract-fulfillment"
              body={{ instant: doc.instant }}
              description="POST /demo/contract-fulfillment — the deterministic full-chain demonstration document for one instant."
            />
            <p className="text-xs leading-relaxed text-ink-faint">
              The read-only variant is the GET form (no body, the default
              instant) — the same call this journey fetched its document
              with, and the one the interactive tour uses.
            </p>
            <Link
              href="/developers/explorer?operation=demo_contract_fulfillment"
              className="inline-flex min-h-11 w-fit items-center rounded-md bg-accent px-4 text-sm font-medium text-accent-ink transition-colors hover:bg-accent-strong"
            >
              Open it in the API Explorer
            </Link>
          </ObjectSection>
        ) : null}
      </DocumentRequired>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Step 9 — Finish with clear next paths
 * ------------------------------------------------------------------ */

/** The next paths — composed from the W1 registries and real routes. */
export function quickstartNextPaths(): LearningLink[] {
  const firstGuide = getGuide("first-connectivity-application");
  return [
    {
      kind: "guide",
      id: "first-connectivity-application",
      label: firstGuide ? firstGuide.title : "Build my first connectivity application",
    },
    { kind: "docs", id: "api", label: "Build with the API" },
    { kind: "route", id: "/connectivity", label: "Operate contracts" },
    { kind: "docs", id: "concepts", label: "Read the concepts" },
    { kind: "docs", id: "troubleshooting", label: "Diagnose a failure" },
    { kind: "route", id: "/", label: "Open the expert workbench" },
  ];
}

export function NextPathsStep() {
  return (
    <div className="flex flex-col gap-4">
      <StepIntro title="Where to go next">
        You have seen the whole lifecycle — requirement to evidence, every
        object real, every claim classed. The paths below are where the
        journey continues; the expert workbench stays one click away.
      </StepIntro>

      <ObjectSection
        title="Your next paths"
        description="Registry-composed links — the guide, the API docs, the workspaces and the docs sections."
      >
        <NextSteps links={quickstartNextPaths()} />
        <p className="text-xs leading-relaxed text-ink-faint">
          Prefer to watch the chain reveal itself stage by stage? Take the{" "}
          <Link
            href="/tour"
            className="text-accent transition-colors hover:text-ink"
          >
            interactive fulfillment tour
          </Link>
          .
        </p>
      </ObjectSection>
    </div>
  );
}
