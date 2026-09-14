"use client";

/**
 * QuickstartView — the canonical beginner journey (the frozen V2 design
 * §6; plan Task 5): nine full-height guided steps from "connect or
 * enter the demo context" to "clear next paths", completable without
 * prior architecture knowledge.
 *
 * The DEC-0128 program, Tasks 4-5 wave, Task 5 of the frozen plan.
 * Discipline:
 *
 * - the ONLY data fetch is the typed client's `demoContractFulfillment`
 *   GET (the default-instant, read-only platform document — no session,
 *   no invented objects); the step bodies in ./quickstart-steps render
 *   from that document and the W1 registries alone;
 * - progress lives in React state ONLY — a reload restarts the journey
 *   at step 1 honestly (the page says so; nothing is persisted);
 * - Back/Continue are native buttons (keyboard operable), and the
 *   journey never dead-ends: step 9 is the next-paths surface itself;
 * - when the demonstration read fails, every document-backed step shows
 *   the canonical ErrorState with a working Retry (§17).
 *
 * This file owns the journey CHROME (step state, progress, navigation);
 * the step bodies live in ./quickstart-steps (same quickstart* file
 * family; the playbooks barrel belongs to W3 and is not touched).
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import { useSession } from "@/lib/session";
import { useAdcosRead } from "@/features/eligibility";
import { parseDemoDocument } from "@/features/fulfillment";
import {
  ApiReproduceStep,
  ConnectStep,
  ContractStep,
  EligibilityStep,
  EvidenceStep,
  NextPathsStep,
  PlanStep,
  QUICKSTART_STEP_TEST_ID,
  RequirementStep,
  RunStep,
} from "./quickstart-steps";

/** Stable test id for the Back control. */
export const QUICKSTART_BACK_TEST_ID = "quickstart-back";

/** Stable test id for the Continue control. */
export const QUICKSTART_CONTINUE_TEST_ID = "quickstart-continue";

/** The nine steps (the frozen design §6 order, verbatim intent). */
export const QUICKSTART_STEPS = [
  { step: 1, title: "Connect or enter the demo context" },
  { step: 2, title: "Describe a connectivity requirement" },
  { step: 3, title: "Review the canonical contract representation" },
  { step: 4, title: "Explain eligibility and provider/policy reasoning" },
  { step: 5, title: "Show the generated fulfillment plan" },
  { step: 6, title: "Run or observe fulfillment" },
  { step: 7, title: "Inspect evidence and assurance" },
  { step: 8, title: "Reproduce an operation through the API Explorer" },
  { step: 9, title: "Finish with clear next paths" },
] as const;

const LAST_STEP = QUICKSTART_STEPS[QUICKSTART_STEPS.length - 1].step;

export function QuickstartView() {
  const { client } = useSession();
  const [step, setStep] = useState<number>(1);

  // the journey's single demonstration read — the GET form (default
  // instant, read-only, no authentication): the same typed client call
  // every console demo surface makes.
  const read = useAdcosRead(
    () => client.demoContractFulfillment(),
    [client],
  );
  const doc = read.data ?? null;
  const view = useMemo(() => (doc ? parseDemoDocument(doc) : null), [doc]);

  const current = QUICKSTART_STEPS.find((entry) => entry.step === step);
  const docProps = {
    doc,
    view,
    readError: read.error,
    onRetryRead: read.refresh,
  };

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <header className="mb-6">
        <h1 className="text-xl font-semibold">Quickstart</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-muted">
          The guided first journey — nine steps from a connectivity
          requirement to inspectable evidence, through the real API. It
          runs end to end in the deterministic demo context: no
          credential needed, nothing fabricated.
        </p>
      </header>

      {/* the journey progress — state only, never persisted */}
      <nav
        aria-label="Quickstart progress"
        className="mb-4 flex flex-wrap items-center gap-2"
      >
        <span className="font-mono text-2xs text-ink-faint">
          step {step} of {LAST_STEP}
        </span>
        <ol className="flex flex-wrap items-center gap-1" aria-hidden="true">
          {QUICKSTART_STEPS.map((entry) => (
            <li key={entry.step}>
              <span
                className={
                  entry.step < step
                    ? "h-1.5 w-5 rounded bg-accent"
                    : entry.step === step
                      ? "h-1.5 w-8 rounded bg-accent-strong"
                      : "h-1.5 w-5 rounded bg-line-strong"
                }
              />
            </li>
          ))}
        </ol>
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">
          {current?.title}
        </span>
      </nav>

      {/* the step body */}
      <div
        data-testid={QUICKSTART_STEP_TEST_ID}
        aria-live="polite"
        className="flex min-h-[24rem] flex-col"
      >
        {step === 1 ? <ConnectStep /> : null}
        {step === 2 ? <RequirementStep /> : null}
        {step === 3 ? <ContractStep {...docProps} /> : null}
        {step === 4 ? <EligibilityStep {...docProps} /> : null}
        {step === 5 ? <PlanStep {...docProps} /> : null}
        {step === 6 ? <RunStep {...docProps} /> : null}
        {step === 7 ? <EvidenceStep {...docProps} /> : null}
        {step === 8 ? <ApiReproduceStep {...docProps} /> : null}
        {step === 9 ? <NextPathsStep /> : null}
      </div>

      {/* the journey navigation — keyboard operable native buttons */}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <button
          type="button"
          data-testid={QUICKSTART_BACK_TEST_ID}
          onClick={() => setStep((value) => Math.max(1, value - 1))}
          disabled={step === 1}
          className="inline-flex min-h-11 items-center rounded-md border border-line-strong bg-raised px-4 text-sm text-ink transition-colors hover:bg-surface disabled:cursor-not-allowed disabled:opacity-50"
        >
          ← Back
        </button>
        <p className="order-last w-full text-center text-2xs text-ink-faint sm:order-none sm:w-auto sm:text-left">
          Progress lives in this page only — a reload restarts the journey
          at step 1. Nothing is persisted.
        </p>
        {step < LAST_STEP ? (
          <button
            type="button"
            data-testid={QUICKSTART_CONTINUE_TEST_ID}
            onClick={() =>
              setStep((value) => Math.min(LAST_STEP, value + 1))
            }
            className="inline-flex min-h-11 items-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-ink transition-colors hover:bg-accent-strong"
          >
            Continue →
          </button>
        ) : (
          <Link
            href="/"
            className="inline-flex min-h-11 items-center rounded-md border border-line-strong bg-raised px-4 text-sm text-ink transition-colors hover:bg-surface"
          >
            Back to the workbench
          </Link>
        )}
      </div>
    </div>
  );
}
