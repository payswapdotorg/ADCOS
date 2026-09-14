"use client";

/**
 * ObjectEducation — the reusable OBJECT-LEVEL explanatory header that
 * renders BEFORE the raw fields on object pages (V2 design §14: "teach
 * the object before exposing its complete fields").
 *
 * The Console V2 learning primitives — DEC-0128, Task 2 of the frozen
 * plan. This is a LAYOUT primitive: the props carry the content (W2/W3
 * object pages compute them from real objects); it never fetches, never
 * reads a store, and adds no business semantics of its own. The only
 * registry touch is the ConceptLink slot (`conceptId`), which renders the
 * inline "What is this?" affordance for the object's concept — or the
 * honest unknown state when the id is not in the registry.
 *
 * Renders: the titled intro ("A connectivity contract describes…"), then
 * the optional fixed rows — lifecycle position, what the user requested,
 * why it matters — then any extra `sections`, and finally the children:
 * the raw structured representation, visually separated below the
 * education. Absent props render no row (honest absence, not filler).
 */

import type { ReactNode } from "react";
import { ConceptLink } from "./concept-link";

/** Stable test id for the object education header. */
export const OBJECT_EDUCATION_TEST_ID = "object-education";

/** One extra explanatory row (e.g. "Evidence and assurance"). */
export interface ObjectEducationSection {
  heading: string;
  body: ReactNode;
}

/** The label each fixed row carries (plain, honest, non-decorative). */
const ROW_LABEL_CLASS = "text-xs text-ink-faint";
const ROW_VALUE_CLASS = "min-w-0 break-words text-xs text-ink";

/**
 * ObjectEducation — the educational header plus the raw representation.
 * `children` (the raw structured fields) always render BELOW the
 * education, separated by a hairline, so the object teaches itself
 * before exposing its machinery.
 */
export function ObjectEducation({
  title,
  intro,
  lifecyclePosition,
  whatUserRequested,
  whyItMatters,
  sections,
  conceptId,
  headingLevel = "h2",
  children,
}: {
  /** The object's own title (e.g. "Connectivity contract"). */
  title: string;
  /** The one-paragraph "A <kind> describes…" intro. */
  intro: ReactNode;
  /** Where the object sits in the console lifecycle. */
  lifecyclePosition?: ReactNode;
  /** What the user actually asked for (computed by the page). */
  whatUserRequested?: ReactNode;
  /** Why this object matters to the developer. */
  whyItMatters?: ReactNode;
  /** Extra explanatory rows specific to the object kind. */
  sections?: ObjectEducationSection[];
  /** The concept registry id for the "What is this?" slot. */
  conceptId?: string;
  /** The intro title's heading level (h2 under a page h1 by default). */
  headingLevel?: "h2" | "h3";
  /** The raw structured representation, rendered below the education. */
  children?: ReactNode;
}) {
  const hasRows =
    lifecyclePosition !== undefined ||
    whatUserRequested !== undefined ||
    whyItMatters !== undefined ||
    (sections !== undefined && sections.length > 0);

  return (
    <section
      data-testid={OBJECT_EDUCATION_TEST_ID}
      className="rounded-md border border-line bg-surface px-4 py-3.5"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {headingLevel === "h2" ? (
          <h2 className="text-base font-semibold text-ink">{title}</h2>
        ) : (
          <h3 className="text-base font-semibold text-ink">{title}</h3>
        )}
        {conceptId !== undefined ? <ConceptLink id={conceptId} /> : null}
      </div>
      <p className="mt-2 text-sm leading-relaxed text-ink-muted">{intro}</p>
      {hasRows ? (
        <dl className="mt-3 flex flex-col gap-2">
          {lifecyclePosition !== undefined ? (
            <div className="grid grid-cols-[minmax(120px,auto)_1fr] gap-x-3">
              <dt className={ROW_LABEL_CLASS}>Lifecycle position</dt>
              <dd className={ROW_VALUE_CLASS}>{lifecyclePosition}</dd>
            </div>
          ) : null}
          {whatUserRequested !== undefined ? (
            <div className="grid grid-cols-[minmax(120px,auto)_1fr] gap-x-3">
              <dt className={ROW_LABEL_CLASS}>What you requested</dt>
              <dd className={ROW_VALUE_CLASS}>{whatUserRequested}</dd>
            </div>
          ) : null}
          {whyItMatters !== undefined ? (
            <div className="grid grid-cols-[minmax(120px,auto)_1fr] gap-x-3">
              <dt className={ROW_LABEL_CLASS}>Why it matters</dt>
              <dd className={ROW_VALUE_CLASS}>{whyItMatters}</dd>
            </div>
          ) : null}
          {sections !== undefined
            ? sections.map((section) => (
                <div
                  key={section.heading}
                  className="grid grid-cols-[minmax(120px,auto)_1fr] gap-x-3"
                >
                  <dt className={ROW_LABEL_CLASS}>{section.heading}</dt>
                  <dd className={ROW_VALUE_CLASS}>{section.body}</dd>
                </div>
              ))
            : null}
        </dl>
      ) : null}
      {children !== undefined ? (
        <div className="mt-4 border-t border-line pt-4">{children}</div>
      ) : null}
    </section>
  );
}
