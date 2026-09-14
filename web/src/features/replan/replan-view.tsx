"use client";
import "@/features/eligibility/fetch-binding-shim";

/**
 * The Replanning surface — an HONEST explainable page, not a dashboard of
 * fabricated events.
 *
 * The frozen UX spec's replan/failover requirement: make autonomous
 * changes explicit — violated requirement or threshold, observed versus
 * required value, detection time, candidates, eligibility/policy
 * reasoning, proposed action/state and supporting evidence; never present
 * a provider handoff as an unexplained side effect.
 *
 * This deployment exposes NO replan decisions through any accepted
 * surface. The page says so plainly (the current truth), explains what
 * replanning is and what would trigger it, and shows the card shape it
 * will render — clearly labeled as a structure preview with placeholder
 * em-dashes only, so it can never be mistaken for data.
 */

import Link from "next/link";
import { ObjectSection } from "@/features/eligibility";

/** The current deployment's position — stated verbatim, never softened. */
export const REPLAN_CURRENT_TRUTH =
  "No replan decisions are exposed by this deployment yet. When the backend exposes them they will appear here.";

/** The wireframe label — it must be unmistakable that this is not data. */
export const REPLAN_WIREFRAME_LABEL =
  "Structure preview — no replan events exist to render";

/** The card shape a replan decision will render (labels only, em-dashes). */
const WIREFRAME_FIELDS = [
  { label: "violated requirement", placeholder: "—" },
  { label: "observed vs required value", placeholder: "— / —" },
  { label: "detection time", placeholder: "—" },
  { label: "candidates", placeholder: "—" },
  { label: "eligibility/policy reasoning", placeholder: "—" },
  { label: "proposed action/state", placeholder: "—" },
  { label: "evidence links", placeholder: "—" },
] as const;

const TRIGGERS = [
  {
    title: "A violated requirement or threshold",
    description:
      "A hard-constraint bound observed outside its limit during fulfillment — the decision carries the observed versus required value and the detection time.",
  },
  {
    title: "Provider unavailability or degradation",
    description:
      "The provider behind the active plan's segment can no longer serve the accepted offer it was composed over.",
  },
  {
    title: "Validity-driven change",
    description:
      "The contract's validity window or the plan's validity no longer covers the fulfillment obligation the contract carries.",
  },
] as const;

export function ReplanView() {
  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <h1 className="sr-only">Replanning</h1>
      <Link
        href="/fulfillment"
        className="mb-4 inline-flex text-sm text-ink-muted transition-colors hover:text-ink"
      >
        ← Fulfillment
      </Link>
      <header className="mb-6">
        <p className="font-mono text-2xs uppercase tracking-wide text-ink-faint">
          Fulfillment · Replan
        </p>
        <h2 className="mt-1 text-xl font-semibold">Replanning</h2>
        <p className="mt-1 text-sm text-ink-muted">
          An honest explainable surface: what replanning is, what would
          trigger it, and exactly what this deployment exposes today. No
          replan events are fabricated.
        </p>
      </header>

      <div className="flex flex-col gap-4">
        {/* What replanning is */}
        <ObjectSection
          id="what-replanning-is"
          title="What replanning is"
          description="In the console's own words — an explanation, not a backend note."
        >
          <p className="text-sm leading-relaxed text-ink-muted">
            Replanning is the explicit re-composition of an accepted
            contract&apos;s fulfillment: a new execution plan composed over
            the same canonical hard constraints when fulfillment conditions
            change. The contract&apos;s constraints are never weakened by a
            replan — the plan-verification gate re-verifies every candidate
            plan preserves them. A provider handoff is never an unexplained
            side effect: every replan decision is presented with its
            reasoning and its supporting evidence, so an operator can always
            answer what changed, why, and on what grounds.
          </p>
        </ObjectSection>

        {/* What would trigger it */}
        <ObjectSection
          id="replan-triggers"
          title="What would trigger it"
          description="The trigger vocabulary a replan decision carries — presented generically; none of these has fired in this deployment."
        >
          <ul className="flex flex-col divide-y divide-line rounded-md border border-line bg-surface">
            {TRIGGERS.map((trigger) => (
              <li key={trigger.title} className="px-4 py-3">
                <p className="text-sm font-medium text-ink">{trigger.title}</p>
                <p className="mt-0.5 text-sm leading-relaxed text-ink-muted">
                  {trigger.description}
                </p>
              </li>
            ))}
          </ul>
        </ObjectSection>

        {/* The current truth — visually distinct, like software evidence */}
        <section
          aria-labelledby="replan-current-truth-heading"
          className="rounded-md border border-dashed border-warning/60 bg-warning/5 px-4 py-4"
        >
          <h2
            id="replan-current-truth-heading"
            className="text-sm font-semibold text-warning"
          >
            The current truth
          </h2>
          <p
            data-testid="replan-current-truth"
            className="mt-1 text-sm leading-relaxed text-ink"
          >
            {REPLAN_CURRENT_TRUTH}
          </p>
        </section>

        {/* The card shape, ready — a labeled wireframe, never real-looking */}
        <ObjectSection
          id="replan-card-shape"
          title="The card shape, ready"
          description="What a replan decision card will render here — a wireframe with placeholder values only."
        >
          <div
            data-testid="replan-wireframe"
            className="rounded-md border border-dashed border-line bg-raised/60 px-3 py-3"
          >
            <p className="font-mono text-2xs uppercase tracking-wide text-ink-faint">
              {REPLAN_WIREFRAME_LABEL}
            </p>
            <dl className="mt-2.5 grid gap-2.5">
              {WIREFRAME_FIELDS.map((field) => (
                <div
                  key={field.label}
                  className="grid grid-cols-[minmax(13rem,auto)_1fr] items-baseline gap-x-3"
                >
                  <dt className="break-all font-mono text-2xs text-ink-faint">
                    {field.label}
                  </dt>
                  <dd className="font-mono text-xs text-ink-faint">
                    {field.placeholder}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
          <p className="text-xs leading-relaxed text-ink-faint">
            The placeholder values are em-dashes on purpose: when the backend
            exposes replan decisions, each card renders the fields above from
            the decision record and links to the underlying contract, plan
            and evidence.
          </p>
        </ObjectSection>
      </div>
    </div>
  );
}
