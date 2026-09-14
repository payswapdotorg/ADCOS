"use client";

/**
 * FulfillmentTourView — the interactive product tour (the frozen V2
 * design §7; plan Task 5): the deterministic fulfillment demonstration
 * transformed into a step-by-step TEACHING surface.
 *
 * The DEC-0128 program, Tasks 4-5 wave, Task 5 of the frozen plan. A
 * realistic requirement is presented, then the system reveals itself
 * stage by stage:
 *
 * `Requirement → Eligibility → Plan → Execution → Evidence → Assurance`
 *
 * At EVERY stage the user can open (the §7 pattern):
 * - **Explain this** — the stage's concept education, through the W1
 *   ConceptExplainer drawer (registry content only, never re-authored);
 * - **View object** — the real DemoDocument slice (JsonViewer);
 * - **View API request** / **View API response** — the real pair: the
 *   typed client call this tour made (GET /demo/contract-fulfillment,
 *   the read-only platform read) and the returned document;
 * - **Continue** (and Back) — native buttons, keyboard operable.
 *
 * The tour calls the SAME typed client method every console demo
 * surface calls — `demoContractFulfillment()` with no instant (GET, the
 * default document) — once, and renders purely from what came back:
 * identical document → identical tour (determinism stated plainly).
 *
 * The tour ENDS with the evidence-class honesty note (SOFTWARE;
 * physical/network NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT — the V1 legend
 * vocabulary) and the next paths. §17 throughout: no fabricated
 * provider, no invented objects, SOFTWARE evidence never presented as
 * physical/network evidence.
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import { useSession } from "@/lib/session";
import type { DemoDocument } from "@/lib/api/types";
import { getConcept } from "@/lib/education";
import type { LearningLink } from "@/lib/education";
import {
  ConceptExplainer,
  NextSteps,
} from "@/features/learning";
import {
  DEMO_DETERMINISM_NOTE,
  parseDemoDocument,
  type DemoDocumentView,
} from "@/features/fulfillment";
import { NOT_ACHIEVABLE_BY_THIS_DEPLOYMENT } from "@/features/evidence";
import { useAdcosRead } from "@/features/eligibility";
import {
  ApiRequestPanel,
  ErrorState,
  EvidenceBadge,
  JsonViewer,
} from "@/components/ui";
import { cn } from "@/lib/utils";

/** Stable test ids for the tour suite. */
export const TOUR_STAGE_TEST_ID = "tour-stage";
export const TOUR_BACK_TEST_ID = "tour-back";
export const TOUR_CONTINUE_TEST_ID = "tour-continue";
export const TOUR_END_TEST_ID = "tour-end";
export const TOUR_OBJECT_PANEL_TEST_ID = "tour-object-panel";
export const TOUR_REQUEST_PANEL_TEST_ID = "tour-request-panel";
export const TOUR_RESPONSE_PANEL_TEST_ID = "tour-response-panel";

/** The tour's read (the same typed client call, GET form). */
export const TOUR_REQUEST = {
  method: "GET",
  path: "/demo/contract-fulfillment",
} as const;

/**
 * The six stages (frozen design §7, verbatim stage names), each bound
 * to its W1 registry concept and its DemoDocument slice. The Assurance
 * slice is the contract's own assurance_obligations member — the real
 * referenced material, never an evaluated invention.
 */
export const TOUR_STAGES = [
  {
    stage: "Requirement",
    conceptId: "connectivity-contract",
    slice: "contract",
    sliceName: "contract",
  },
  {
    stage: "Eligibility",
    conceptId: "eligibility",
    slice: "boundary",
    sliceName: "boundary",
  },
  {
    stage: "Plan",
    conceptId: "execution-plan",
    slice: "plan",
    sliceName: "plan",
  },
  {
    stage: "Execution",
    conceptId: "fulfillment",
    slice: "execution",
    sliceName: "execution",
  },
  {
    stage: "Evidence",
    conceptId: "evidence",
    slice: "evidence",
    sliceName: "evidence",
  },
  {
    stage: "Assurance",
    conceptId: "assurance",
    slice: "assurance",
    sliceName: "assurance_obligations",
  },
] as const;

export type TourStage = (typeof TOUR_STAGES)[number];

const LAST_STAGE_INDEX = TOUR_STAGES.length - 1;

/** The stage's slice of the real document (Assurance reads the contract member). */
function stageSlice(doc: DemoDocument, stage: TourStage): unknown {
  if (stage.slice === "assurance") {
    return (doc.contract as Record<string, unknown>)
      .assurance_obligations;
  }
  return doc[stage.slice];
}

/* ------------------------------------------------------------------ *
 * Per-stage facts (presentation reads of the parsed view — verbatim)
 * ------------------------------------------------------------------ */

function StageFacts({
  stage,
  doc,
  view,
}: {
  stage: TourStage;
  doc: DemoDocument;
  view: DemoDocumentView;
}) {
  switch (stage.slice) {
    case "contract":
      return (
        <dl className="grid grid-cols-[minmax(9rem,auto)_1fr] items-baseline gap-x-3 gap-y-1.5">
          <dt className="font-mono text-2xs text-ink-faint">state</dt>
          <dd className="font-mono text-xs text-ink">
            {view.contract.state}
          </dd>
          <dt className="font-mono text-2xs text-ink-faint">
            hard_constraints
          </dt>
          <dd className="font-mono text-xs text-ink">
            {view.contract.hard_constraints
              .map(
                (constraint) =>
                  `${constraint.kind} ${JSON.stringify(constraint.params)}`,
              )
              .join(" · ") || "none"}
          </dd>
          <dt className="font-mono text-2xs text-ink-faint">validity</dt>
          <dd className="font-mono text-xs text-ink">
            {view.contract.validity
              ? `${view.contract.validity.not_before} → ${view.contract.validity.not_after}`
              : "—"}
          </dd>
          <dt className="font-mono text-2xs text-ink-faint">
            evidence_class
          </dt>
          <dd>
            <EvidenceBadge evidenceClass={doc.evidence_class} size="sm" />
          </dd>
        </dl>
      );
    case "boundary":
      return (
        <ul className="flex flex-col gap-1.5">
          {doc.boundary.map((entry) => (
            <li
              key={entry.request_id}
              className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5"
            >
              <span className="rounded border border-line-strong px-1 font-mono text-2xs text-ink-muted">
                {entry.method}
              </span>
              <span className="break-all font-mono text-xs text-ink">
                {entry.route}
              </span>
              <span className="font-mono text-2xs text-ink-faint">
                {String(entry.status)}
              </span>
            </li>
          ))}
          <li className="text-xs leading-relaxed text-ink-faint">
            The boundary leg drove the canonical lifecycle (intent →
            offer → activation) — this trace is the capability reasoning
            this deployment exposes.
          </li>
        </ul>
      );
    case "plan":
      return (
        <dl className="grid grid-cols-[minmax(9rem,auto)_1fr] items-baseline gap-x-3 gap-y-1.5">
          <dt className="font-mono text-2xs text-ink-faint">plan_id</dt>
          <dd className="break-all font-mono text-xs text-ink">
            {view.plan.plan_id}
          </dd>
          <dt className="font-mono text-2xs text-ink-faint">
            constraint_fingerprint
          </dt>
          <dd className="break-all font-mono text-xs text-ink">
            {view.plan.constraint_fingerprint}
          </dd>
          <dt className="font-mono text-2xs text-ink-faint">segments</dt>
          <dd className="font-mono text-xs text-ink">
            {view.plan.segments
              .map(
                (segment) =>
                  `${segment.role}: ${segment.operations.join(" → ")}`,
              )
              .join(" · ") || "none"}
          </dd>
        </dl>
      );
    case "execution":
      return (
        <dl className="grid grid-cols-[minmax(9rem,auto)_1fr] items-baseline gap-x-3 gap-y-1.5">
          <dt className="font-mono text-2xs text-ink-faint">provider</dt>
          <dd className="font-mono text-xs text-ink">
            {view.execution.provider}
          </dd>
          <dt className="font-mono text-2xs text-ink-faint">
            segment_states
          </dt>
          <dd className="font-mono text-xs text-ink">
            {view.execution.segment_states.join(" → ") || "—"}
          </dd>
          <dt className="font-mono text-2xs text-ink-faint">samples</dt>
          <dd className="font-mono text-xs text-ink">
            {view.execution.samples.length}
          </dd>
          <dt className="font-mono text-2xs text-ink-faint">sandbox</dt>
          <dd className="font-mono text-xs text-ink">
            {String(view.execution.sandbox ?? "—")}
          </dd>
        </dl>
      );
    case "evidence":
      return (
        <dl className="grid grid-cols-[minmax(9rem,auto)_1fr] items-baseline gap-x-3 gap-y-1.5">
          <dt className="font-mono text-2xs text-ink-faint">records</dt>
          <dd className="font-mono text-xs text-ink">
            {view.evidence.length}
          </dd>
          <dt className="font-mono text-2xs text-ink-faint">
            record_types
          </dt>
          <dd className="font-mono text-xs text-ink">
            {view.evidence.map((record) => record.record_type).join(" · ") ||
              "—"}
          </dd>
          <dt className="font-mono text-2xs text-ink-faint">
            evidence_class
          </dt>
          <dd>
            <EvidenceBadge evidenceClass={doc.evidence_class} size="sm" />
          </dd>
        </dl>
      );
    case "assurance":
      return (
        <ul className="flex flex-col gap-1.5">
          {view.contract.assurance_obligations.length === 0 ? (
            <li className="text-sm text-ink-faint">
              no assurance obligations referenced
            </li>
          ) : (
            view.contract.assurance_obligations.map((obligation) => (
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
              </li>
            ))
          )}
          <li className="text-xs leading-relaxed text-ink-faint">
            Referenced material, never evaluated here — assurance
            semantics belong to the issuing authority, and the console
            renders the references verbatim.
          </li>
        </ul>
      );
  }
}

/* ------------------------------------------------------------------ *
 * One stage screen — the four §7 affordances
 * ------------------------------------------------------------------ */

/** The toggle-button presentation (View object / View API request / response). */
const TOGGLE_CLASSES =
  "inline-flex min-h-11 items-center rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface";

function StageScreen({
  stage,
  stageIndex,
  doc,
  view,
  onBack,
  onContinue,
  isLast,
}: {
  stage: TourStage;
  stageIndex: number;
  doc: DemoDocument;
  view: DemoDocumentView;
  onBack: () => void;
  onContinue: () => void;
  isLast: boolean;
}) {
  const concept = getConcept(stage.conceptId);
  const [showObject, setShowObject] = useState(false);
  const [showRequest, setShowRequest] = useState(false);
  const [showResponse, setShowResponse] = useState(false);

  return (
    <div className="flex flex-col gap-4" data-testid={TOUR_STAGE_TEST_ID}>
      <div className="flex flex-col gap-1.5">
        <p className="font-mono text-2xs uppercase tracking-wide text-ink-faint">
          stage {stageIndex + 1} of {TOUR_STAGES.length} —{" "}
          {stage.stage}
        </p>
        <h2 className="text-lg font-semibold text-ink">{stage.stage}</h2>
        <p className="max-w-3xl text-sm leading-relaxed text-ink-muted">
          {concept
            ? concept.summary
            : `No concept education is recorded for ${stage.conceptId} — nothing is invented.`}
        </p>
      </div>

      <div className="rounded-md border border-line bg-surface px-4 py-3">
        <StageFacts stage={stage} doc={doc} view={view} />
      </div>

      {/* the four affordances (§7) */}
      <div className="flex flex-wrap items-center gap-2">
        <ConceptExplainer
          id={stage.conceptId}
          mode="drawer"
          trigger={({ ref, open, onToggle }) => (
            <button
              ref={ref}
              type="button"
              data-testid="tour-explain"
              onClick={onToggle}
              aria-haspopup="dialog"
              aria-expanded={open}
              className="inline-flex min-h-11 items-center rounded-md bg-accent px-3 text-sm font-medium text-accent-ink transition-colors hover:bg-accent-strong"
            >
              Explain this
            </button>
          )}
        />
        <button
          type="button"
          data-testid="tour-view-object"
          onClick={() => setShowObject((value) => !value)}
          aria-expanded={showObject}
          className={TOGGLE_CLASSES}
        >
          View object
        </button>
        <button
          type="button"
          data-testid="tour-view-request"
          onClick={() => setShowRequest((value) => !value)}
          aria-expanded={showRequest}
          className={TOGGLE_CLASSES}
        >
          View API request
        </button>
        <button
          type="button"
          data-testid="tour-view-response"
          onClick={() => setShowResponse((value) => !value)}
          aria-expanded={showResponse}
          className={TOGGLE_CLASSES}
        >
          View API response
        </button>
      </div>

      {showObject ? (
        <div
          data-testid={TOUR_OBJECT_PANEL_TEST_ID}
          className="rounded-md border border-line bg-surface px-4 py-3"
        >
          <p className="mb-2 text-xs text-ink-muted">
            The real <span className="font-mono">{stage.sliceName}</span>{" "}
            slice of the demonstration document — verbatim.
          </p>
          <JsonViewer
            value={stageSlice(doc, stage)}
            name={stage.sliceName}
            defaultExpandedDepth={1}
          />
        </div>
      ) : null}

      {showRequest ? (
        <div
          data-testid={TOUR_REQUEST_PANEL_TEST_ID}
          className="rounded-md border border-line bg-surface px-4 py-3"
        >
          <p className="mb-2 text-xs text-ink-muted">
            The request this tour made once at the start — the read-only
            platform GET (no body, no authentication headers).
          </p>
          <ApiRequestPanel
            method={TOUR_REQUEST.method}
            path={TOUR_REQUEST.path}
            variant="full"
          />
        </div>
      ) : null}

      {showResponse ? (
        <div
          data-testid={TOUR_RESPONSE_PANEL_TEST_ID}
          className="rounded-md border border-line bg-surface px-4 py-3"
        >
          <p className="mb-2 text-xs text-ink-muted">
            The response that came back — the full demonstration document
            every stage&apos;s slice comes from.
          </p>
          <JsonViewer value={doc} name="document" defaultExpandedDepth={1} />
        </div>
      ) : null}

      {/* Continue / Back */}
      <div className="mt-2 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <button
          type="button"
          data-testid={TOUR_BACK_TEST_ID}
          onClick={onBack}
          disabled={stageIndex === 0}
          className="inline-flex min-h-11 items-center rounded-md border border-line-strong bg-raised px-4 text-sm text-ink transition-colors hover:bg-surface disabled:cursor-not-allowed disabled:opacity-50"
        >
          ← Back
        </button>
        <button
          type="button"
          data-testid={TOUR_CONTINUE_TEST_ID}
          onClick={onContinue}
          className="inline-flex min-h-11 items-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-ink transition-colors hover:bg-accent-strong"
        >
          {isLast ? "Finish the tour" : "Continue →"}
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * The end screen — honesty note + next paths
 * ------------------------------------------------------------------ */

/** The tour's next paths (registry + real routes). */
export function tourNextPaths(): LearningLink[] {
  return [
    { kind: "docs", id: "quickstart", label: "Take the guided Quickstart" },
    { kind: "route", id: "/fulfillment", label: "Open the Fulfillment workspace" },
    { kind: "route", id: "/evidence", label: "Open the Evidence page" },
    { kind: "concept", id: "evidence", label: "Evidence — SOFTWARE class, honestly labeled" },
    { kind: "route", id: "/", label: "Open the expert workbench" },
  ];
}

function TourEnd() {
  return (
    <div data-testid={TOUR_END_TEST_ID} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <p className="font-mono text-2xs uppercase tracking-wide text-ink-faint">
          the end
        </p>
        <h2 className="text-lg font-semibold text-ink">
          What you just saw — and what it honestly is
        </h2>
      </div>

      <div className="flex flex-col gap-3 rounded-md border border-line bg-surface px-4 py-3.5">
        <div className="flex flex-wrap items-baseline gap-2">
          <span className="text-sm font-medium text-ink">
            Evidence class:
          </span>
          <EvidenceBadge evidenceClass="SOFTWARE" />
          <span className="text-sm text-ink-muted">
            software-side, deterministic — what this deployment produces
          </span>
        </div>
        <p className="text-sm leading-relaxed text-ink-muted">
          Physical/network evidence is{" "}
          <span className="font-mono text-xs text-ink">
            {NOT_ACHIEVABLE_BY_THIS_DEPLOYMENT}
          </span>{" "}
          — it can only come from real provider observations or direct
          measurements, this deployment produces none, and no UI state
          can turn SOFTWARE evidence into a physical PASS.
        </p>
        <p className="text-sm leading-relaxed text-ink-muted">
          {DEMO_DETERMINISM_NOTE}
        </p>
        <p className="text-xs leading-relaxed text-ink-faint">
          The tour re-runs identically for the same document — the stage
          sequence, the object slices and the honesty notes are a pure
          function of what the boundary returned.
        </p>
      </div>

      <div className="rounded-md border border-line bg-surface px-4 py-3.5">
        <h3 className="text-sm font-semibold text-ink">Where to go next</h3>
        <div className="mt-2">
          <NextSteps links={tourNextPaths()} />
        </div>
        <p className="mt-2 text-xs leading-relaxed text-ink-faint">
          Prefer the guided nine-step journey?{" "}
          <Link
            href="/quickstart"
            className="text-accent transition-colors hover:text-ink"
          >
            Open the Quickstart
          </Link>
          .
        </p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * The view
 * ------------------------------------------------------------------ */

export function FulfillmentTourView() {
  const { client } = useSession();
  const [stageIndex, setStageIndex] = useState<number>(0);
  // one past the last stage = the end screen
  const [finished, setFinished] = useState(false);

  // the tour's single read: the SAME typed client call, GET form —
  // read-only, unauthenticated, deterministic.
  const read = useAdcosRead(
    () => client.demoContractFulfillment(),
    [client],
  );
  const doc = read.data ?? null;
  const view = useMemo(() => (doc ? parseDemoDocument(doc) : null), [doc]);

  const stage = TOUR_STAGES[stageIndex];

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <header className="mb-4">
        <h1 className="text-xl font-semibold">The fulfillment tour</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-muted">
          A realistic requirement, then the system revealing itself stage
          by stage — every object real, every request the one this tour
          actually made. Six stages, four affordances each.
        </p>
      </header>

      {/* the stage rail — the §7 sequence, current stage highlighted */}
      <nav
        aria-label="The tour stages"
        className="mb-4 flex flex-wrap items-center gap-1.5"
      >
        {TOUR_STAGES.map((entry, index) => (
          <span key={entry.stage} className="flex items-center gap-1.5">
            {index > 0 ? (
              <span aria-hidden="true" className="text-ink-faint">
                →
              </span>
            ) : null}
            <span
              aria-current={
                !finished && index === stageIndex ? "step" : undefined
              }
              className={cn(
                "rounded border px-2 py-0.5 text-sm",
                finished
                  ? "border-line bg-raised text-ink-faint"
                  : index === stageIndex
                    ? "border-accent bg-accent text-accent-ink"
                    : index < stageIndex
                      ? "border-line-strong bg-raised text-ink-muted"
                      : "border-line bg-raised text-ink-faint",
              )}
            >
              {entry.stage}
            </span>
          </span>
        ))}
      </nav>

      {read.error && !doc ? (
        <section className="rounded-md border border-line bg-surface">
          <ErrorState error={read.error} onRetry={read.refresh} />
          <div className="border-t border-line px-4 py-3">
            <p className="text-xs text-ink-faint">
              The tour renders only real document content — nothing is
              fabricated while the read is unavailable.
            </p>
          </div>
        </section>
      ) : !doc || !view ? (
        <div className="flex flex-col gap-4" aria-busy="true">
          {[0, 1, 2].map((index) => (
            <div
              key={index}
              className="h-24 animate-pulse rounded-md border border-line bg-surface"
            />
          ))}
        </div>
      ) : finished ? (
        <TourEnd />
      ) : (
        <StageScreen
          stage={stage}
          stageIndex={stageIndex}
          doc={doc}
          view={view}
          onBack={() => setStageIndex((value) => Math.max(0, value - 1))}
          onContinue={() => {
            if (stageIndex === LAST_STAGE_INDEX) {
              setFinished(true);
            } else {
              setStageIndex((value) =>
                Math.min(LAST_STAGE_INDEX, value + 1),
              );
            }
          }}
          isLast={stageIndex === LAST_STAGE_INDEX}
        />
      )}

      {finished ? (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
          <button
            type="button"
            data-testid={TOUR_BACK_TEST_ID}
            onClick={() => {
              setFinished(false);
              setStageIndex(LAST_STAGE_INDEX);
            }}
            className="inline-flex min-h-11 items-center rounded-md border border-line-strong bg-raised px-4 text-sm text-ink transition-colors hover:bg-surface"
          >
            ← Back
          </button>
          <p className="order-last w-full text-center text-2xs text-ink-faint sm:order-none sm:w-auto sm:text-left">
            Tour position lives in this page only — a reload restarts at
            the Requirement stage.
          </p>
          <Link
            href="/"
            className="inline-flex min-h-11 items-center rounded-md border border-line-strong bg-raised px-4 text-sm text-ink transition-colors hover:bg-surface"
          >
            Back to the workbench
          </Link>
        </div>
      ) : null}
    </div>
  );
}
