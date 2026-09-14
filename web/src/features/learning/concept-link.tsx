"use client";

/**
 * ConceptLink — the inline "What is this?" affordance (V2 design §10,
 * the first approved contextual-education pattern).
 *
 * The Console V2 learning primitives — DEC-0128, Task 2 of the frozen
 * plan. This is a PURE PRESENTATION primitive over the Task-1 education
 * registry (`@/lib/education`): it never fetches, never touches a store,
 * and never invents a definition — every string it renders comes from
 * `getConcept`. Composing ConceptExplainer's drawer mode means the
 * explanation opens WITHOUT leaving the current task (the approved
 * documentation-drawer pattern), with all focus management living in
 * exactly one place.
 *
 * Unknown concept ids (getConcept → undefined) render the HONEST unknown
 * state (design §17): a disabled affordance naming the raw id, never a
 * fabricated definition and never a crash. `UNKNOWN_CONCEPT_TEST_ID` is
 * the stable test hook for that state (shared with ConceptExplainer).
 */

import type { ReactNode } from "react";
import { getConcept } from "@/lib/education";
import { ConceptExplainer } from "./concept-explainer";

/** Stable test id for the honest unknown-concept state (both primitives). */
export const UNKNOWN_CONCEPT_TEST_ID = "concept-unknown";

/**
 * The quiet inline presentation: dotted underline (distinct from real
 * navigation links), and a vertically-extended pseudo-element hit area so
 * the affordance meets the ≥ 44px touch-target bar without breaking the
 * text line it sits in.
 */
const INLINE_CLASSES =
  "relative inline-flex items-center gap-1 rounded-sm py-1 " +
  "underline decoration-dotted decoration-ink-faint underline-offset-4 transition-colors " +
  "hover:decoration-ink " +
  "after:absolute after:-inset-y-3 after:left-0 after:right-0 after:content-['']";

/** The chip presentation: a full 44px-target pill carrying the term. */
const CHIP_CLASSES =
  "inline-flex min-h-11 items-center gap-1.5 rounded-md border border-line-strong " +
  "bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface";

/** The unknown presentation shares the affordance look, visibly inert. */
const UNKNOWN_INLINE_CLASSES =
  "relative inline-flex cursor-not-allowed items-center gap-1 rounded-sm py-1 " +
  "font-mono text-xs text-ink-faint underline decoration-dotted decoration-line " +
  "underline-offset-4 after:absolute after:-inset-y-3 after:left-0 after:right-0 after:content-['']";

const UNKNOWN_CHIP_CLASSES =
  "inline-flex min-h-11 cursor-not-allowed items-center gap-1.5 rounded-md border " +
  "border-dashed border-line bg-transparent px-3 font-mono text-xs text-ink-faint";

/**
 * The honest unknown-concept affordance: a DISABLED button (not a focus
 * stop, not operable) whose accessible name carries the RAW id plus the
 * "Unknown concept" explanation, with a title for pointer users. It never
 * renders registry content, because the registry has none for this id.
 */
export function UnknownConceptAffordance({
  id,
  mode = "inline",
}: {
  id: string;
  mode?: "inline" | "chip";
}) {
  return (
    <button
      type="button"
      disabled
      data-testid={UNKNOWN_CONCEPT_TEST_ID}
      aria-label={`Unknown concept: ${id}`}
      title="Unknown concept — this id is not in the console's education registry, so no definition can be shown."
      className={mode === "chip" ? UNKNOWN_CHIP_CLASSES : UNKNOWN_INLINE_CLASSES}
    >
      {id}
      <span aria-hidden="true" className="text-ink-faint">
        ?
      </span>
    </button>
  );
}

/**
 * ConceptLink — the accessible "What is this?" affordance for one concept.
 *
 * `mode` selects the PRESENTATION only: "inline" is the quiet dotted
 * affordance for prose, "chip" is the 44px pill for lists and slots. Both
 * compose ConceptExplainer's drawer mode, so clicking either opens the
 * concept's full education in the documentation drawer (focus moves in on
 * open, Escape closes, focus returns here on close — see concept-explainer).
 *
 * The accessible name always carries the concept's TERM from the registry
 * ("What is: Eligibility"); `children` only changes the visible text.
 */
export function ConceptLink({
  id,
  children,
  mode = "inline",
}: {
  id: string;
  children?: ReactNode;
  mode?: "inline" | "chip";
}) {
  const concept = getConcept(id);
  if (!concept) {
    return <UnknownConceptAffordance id={id} mode={mode} />;
  }
  return (
    <ConceptExplainer
      id={id}
      mode="drawer"
      trigger={({ ref, open, onToggle }) => (
        <button
          ref={ref}
          type="button"
          onClick={onToggle}
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-label={`What is: ${concept.term}`}
          className={mode === "chip" ? CHIP_CLASSES : INLINE_CLASSES}
        >
          {children ?? concept.term}
          <span aria-hidden="true" className="text-ink-faint">
            ?
          </span>
        </button>
      )}
    />
  );
}
