"use client";

/**
 * ConceptExplainer — the full concept education surface (V2 design §8:
 * the learning model fields; §10: the expandable-explanation and
 * documentation-drawer patterns).
 *
 * The Console V2 learning primitives — DEC-0128, Task 2 of the frozen
 * plan. PURE PRESENTATION over the Task-1 education registry
 * (`@/lib/education`): no fetch, no stores, and no invented content —
 * every string rendered comes from the REAL registries (the concept
 * itself, `getOperationEducation`, `getGuide`), with honest verbatim
 * fallbacks when a reference has no registry entry.
 *
 * Modes:
 * - "block"  — an inline section: term heading, summary, then the
 *   progressively-disclosed sections (Why it matters / When to use it /
 *   What happens in ADCOS as aria-expanded disclosures).
 * - "inline" — a compact expandable: one disclosure trigger toggling the
 *   full block below it (keyboard operable, aria-expanded + aria-controls,
 *   Escape collapses).
 * - "drawer" — a trigger plus the V1 ui Drawer (Radix Dialog underneath):
 *   focus moves INTO the drawer on open, a full tab-cycle trap holds it
 *   there (Radix FocusScope), Escape closes, and focus RETURNS to the
 *   trigger on close (restored manually — the V1 Drawer exposes no
 *   Dialog.Trigger slot of its own). The drawer is labelled
 *   "Concept: <term>" via the Drawer's own Dialog.Title conventions.
 *
 * Unknown ids render the honest unknown state (design §17) — an
 * EmptyState disclosure naming the raw id, never a fabricated definition.
 *
 * The optional `trigger` render-prop lets composing primitives own the
 * affordance's presentation (ConceptLink's inline/chip look, NextStep's
 * "Learn: …" label) while the drawer wiring — and therefore ALL focus
 * management — lives in exactly one place.
 */

import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, ReactNode, Ref } from "react";
import Link from "next/link";
import { getConcept, getGuide, getOperationEducation } from "@/lib/education";
import type { ConceptDefinition } from "@/lib/education";
import { cn } from "@/lib/utils";
import {
  AlertIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  Drawer,
  EmptyState,
  ExternalLinkIcon,
} from "@/components/ui";
import { ConceptLink, UNKNOWN_CONCEPT_TEST_ID } from "./concept-link";
import { NextSteps } from "./next-step";

/** Stable test id for the rendered concept education body. */
export const CONCEPT_EDUCATION_TEST_ID = "concept-education";

/** Stable test id for the explainer's own trigger (inline + drawer modes). */
export const CONCEPT_EXPLAINER_TRIGGER_TEST_ID = "concept-explainer-trigger";

/** The props the drawer mode hands to a custom trigger render-prop. */
export interface ConceptExplainerTriggerProps {
  /** Attach to the trigger button — focus returns to it on drawer close. */
  ref: Ref<HTMLButtonElement>;
  /** Whether the drawer is currently open (for aria-expanded). */
  open: boolean;
  /** Opens/closes the drawer. */
  onToggle: () => void;
}

/* ------------------------------------------------------------------ *
 * Shared presentation pieces
 * ------------------------------------------------------------------ */

/** One progressively-disclosed panel: trigger button + collapsible body. */
export function Disclosure({
  heading,
  children,
  defaultOpen = false,
}: {
  heading: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();
  return (
    <div className="overflow-hidden rounded-md border border-line bg-surface">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="flex min-h-11 w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm font-medium text-ink transition-colors hover:bg-raised/40"
      >
        <span>{heading}</span>
        <ChevronDownIcon
          size={14}
          className={cn(
            "shrink-0 text-ink-faint transition-transform",
            open && "rotate-180",
          )}
        />
      </button>
      <div
        id={panelId}
        hidden={!open}
        className="border-t border-line px-3 pb-3 pt-2 text-sm leading-relaxed text-ink-muted"
      >
        {children}
      </div>
    </div>
  );
}

/** A small section heading; only the semantic level differs by context. */
function SectionHeading({
  level,
  children,
}: {
  level: "h3" | "h4";
  children: ReactNode;
}) {
  if (level === "h3") {
    return <h3 className="text-sm font-semibold text-ink">{children}</h3>;
  }
  return <h4 className="text-sm font-semibold text-ink">{children}</h4>;
}

/** One related operation: the id as an API Explorer anchor + its purpose. */
function OperationRef({
  operationId,
  note,
}: {
  operationId: string;
  note?: string;
}) {
  const education = getOperationEducation(operationId);
  return (
    <li className="flex flex-col gap-0.5">
      <Link
        href={`/developers/explorer?operation=${operationId}`}
        className="w-fit font-mono text-xs text-ink underline decoration-line-strong underline-offset-2 transition-colors hover:decoration-ink"
      >
        {operationId}
      </Link>
      <span className="text-sm text-ink-muted">
        {note ?? education?.purpose}
      </span>
      {!education ? (
        <span className="text-xs text-ink-faint">
          no operation education is recorded for this id — the id is shown
          verbatim, nothing is invented for it
        </span>
      ) : null}
    </li>
  );
}

/** One related guide: its registry title as a docs anchor + its purpose. */
function GuideRef({ guideId }: { guideId: string }) {
  const guide = getGuide(guideId);
  return (
    <li className="flex flex-col gap-0.5">
      <Link
        href={`/docs/guides/${guideId}`}
        className="w-fit text-sm text-ink underline decoration-line-strong underline-offset-2 transition-colors hover:decoration-ink"
      >
        Guide: {guide?.title ?? guideId}
      </Link>
      {guide ? (
        <span className="text-sm text-ink-muted">{guide.purpose}</span>
      ) : (
        <span className="text-xs text-ink-faint">
          no guide is recorded for this id — the id is shown verbatim,
          nothing is invented for it
        </span>
      )}
    </li>
  );
}

/**
 * The concept's full education below the term/summary: the three
 * progressively-disclosed long-form sections, then the cross-reference
 * groups (prerequisites as ConceptLink chips, the API look, related
 * objects, related operations, related guides) and "Where to go next".
 * Absent registry data renders NO section — honest absence, not filler.
 */
function ConceptSections({
  concept,
  heading,
}: {
  concept: ConceptDefinition;
  heading: "h3" | "h4";
}) {
  return (
    <div className="flex flex-col gap-3">
      <Disclosure heading="Why it matters">{concept.whyItMatters}</Disclosure>
      <Disclosure heading="When to use it">{concept.whenToUse}</Disclosure>
      <Disclosure heading="What happens in ADCOS">
        {concept.whatHappens}
      </Disclosure>

      {concept.prerequisites.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          <SectionHeading level={heading}>Prerequisites</SectionHeading>
          <ul className="flex flex-wrap gap-2">
            {concept.prerequisites.map((prerequisiteId) => (
              <li key={prerequisiteId}>
                <ConceptLink id={prerequisiteId} mode="chip" />
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {concept.apiLook ? (
        <div className="flex flex-col gap-1.5">
          <SectionHeading level={heading}>What the API looks like</SectionHeading>
          <ul className="flex flex-col gap-1.5">
            <OperationRef
              operationId={concept.apiLook.operationId}
              note={concept.apiLook.note}
            />
          </ul>
        </div>
      ) : null}

      {concept.relatedObjects.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          <SectionHeading level={heading}>Related objects</SectionHeading>
          <ul className="flex flex-wrap gap-1.5">
            {concept.relatedObjects.map((objectName) => (
              <li key={objectName}>
                <code className="inline-flex items-center rounded border border-line-strong bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted">
                  {objectName}
                </code>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {concept.relatedOperations.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          <SectionHeading level={heading}>Related operations</SectionHeading>
          <ul className="flex flex-col gap-1.5">
            {concept.relatedOperations.map((operationId) => (
              <OperationRef key={operationId} operationId={operationId} />
            ))}
          </ul>
        </div>
      ) : null}

      {concept.relatedGuides.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          <SectionHeading level={heading}>Related guides</SectionHeading>
          <ul className="flex flex-col gap-1.5">
            {concept.relatedGuides.map((guideId) => (
              <GuideRef key={guideId} guideId={guideId} />
            ))}
          </ul>
        </div>
      ) : null}

      {concept.nextSteps.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          <SectionHeading level={heading}>Where to go next</SectionHeading>
          <NextSteps links={concept.nextSteps} />
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * The honest unknown state
 * ------------------------------------------------------------------ */

/**
 * The unknown-concept disclosure: an EmptyState naming the RAW id and
 * stating why nothing else is shown. Shares UNKNOWN_CONCEPT_TEST_ID with
 * ConceptLink's unknown affordance — one convention for both primitives.
 */
function UnknownConceptDisclosure({ id }: { id: string }) {
  return (
    <div
      data-testid={UNKNOWN_CONCEPT_TEST_ID}
      className="rounded-md border border-dashed border-line bg-surface"
    >
      <EmptyState
        icon={<AlertIcon size={16} />}
        title="Unknown concept"
        description={
          <>
            The concept id{" "}
            <code className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted">
              {id}
            </code>{" "}
            is not in the console&apos;s education registry. No definition is
            shown rather than an invented one — the registry is the only
            concept authority.
          </>
        }
      />
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * The three modes
 * ------------------------------------------------------------------ */

function ConceptExplainerDrawer({
  concept,
  trigger,
}: {
  concept: ConceptDefinition;
  trigger?: (props: ConceptExplainerTriggerProps) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  // True between "the drawer just closed" and the post-unmount focus
  // restoration — so a drawer that never opened never steals focus.
  const restoreFocusRef = useRef(false);

  // The V1 Drawer composes Radix Dialog, whose unmount-time focus return
  // targets the Dialog's OWN trigger ref — but the Drawer wrapper exposes
  // no Dialog.Trigger slot, so that ref is null and Radix's restore is a
  // no-op. Restoring synchronously in the open-change handler LOSES the
  // race against Radix's still-attached focus trap (a focusout with the
  // trigger as relatedTarget gets pulled straight back into the panel),
  // so the restore runs AFTER the unmount, in an effect, once the trap's
  // listeners are gone — observably returning focus to the affordance
  // that opened the drawer.
  const handleOpenChange = (next: boolean) => {
    if (open && !next) {
      restoreFocusRef.current = true;
    }
    setOpen(next);
  };

  useEffect(() => {
    if (!open && restoreFocusRef.current) {
      restoreFocusRef.current = false;
      triggerRef.current?.focus();
    }
  }, [open]);

  return (
    <>
      {trigger ? (
        trigger({
          ref: triggerRef,
          open,
          onToggle: () => handleOpenChange(!open),
        })
      ) : (
        <button
          ref={triggerRef}
          type="button"
          data-testid={CONCEPT_EXPLAINER_TRIGGER_TEST_ID}
          onClick={() => handleOpenChange(true)}
          aria-haspopup="dialog"
          aria-expanded={open}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface"
        >
          What is: {concept.term}
        </button>
      )}
      <Drawer
        open={open}
        onOpenChange={handleOpenChange}
        title={`Concept: ${concept.term}`}
        description={concept.summary}
        footer={
          <Link
            href={`/docs/concepts/${concept.id}`}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface"
          >
            <ExternalLinkIcon size={14} />
            Open the full documentation
          </Link>
        }
      >
        <ConceptSections concept={concept} heading="h3" />
      </Drawer>
    </>
  );
}

function ConceptExplainerInline({ concept }: { concept: ConceptDefinition }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const headingId = useId();

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "Escape" && open) {
      event.preventDefault();
      setOpen(false);
    }
  };

  return (
    <div className="rounded-md border border-line bg-surface">
      <button
        type="button"
        data-testid={CONCEPT_EXPLAINER_TRIGGER_TEST_ID}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={handleKeyDown}
        className="flex min-h-11 w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm font-medium text-ink transition-colors hover:bg-raised/40"
      >
        <span id={headingId}>What is: {concept.term}?</span>
        <ChevronRightIcon
          size={14}
          className={cn(
            "shrink-0 text-ink-faint transition-transform",
            open && "rotate-90",
          )}
        />
      </button>
      <div id={panelId} hidden={!open} className="border-t border-line px-3 py-3">
        <h4 className="text-base font-semibold text-ink">{concept.term}</h4>
        <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">
          {concept.summary}
        </p>
        <div className="mt-3">
          <ConceptSections concept={concept} heading="h4" />
        </div>
      </div>
    </div>
  );
}

/**
 * ConceptExplainer — renders one concept's full education from the
 * registry, in the mode the composing surface needs. See the file header
 * for the three modes and their accessibility contracts.
 */
export function ConceptExplainer({
  id,
  mode = "block",
  trigger,
}: {
  id: string;
  mode?: "block" | "drawer" | "inline";
  trigger?: (props: ConceptExplainerTriggerProps) => ReactNode;
}) {
  const concept = getConcept(id);
  if (!concept) {
    return <UnknownConceptDisclosure id={id} />;
  }
  if (mode === "drawer") {
    return <ConceptExplainerDrawer concept={concept} trigger={trigger} />;
  }
  if (mode === "inline") {
    return <ConceptExplainerInline concept={concept} />;
  }
  return (
    <section
      data-testid={CONCEPT_EDUCATION_TEST_ID}
      aria-label={`Concept: ${concept.term}`}
      className="rounded-md border border-line bg-surface px-4 py-3.5"
    >
      <h3 className="text-base font-semibold text-ink">{concept.term}</h3>
      <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">
        {concept.summary}
      </p>
      <div className="mt-3">
        <ConceptSections concept={concept} heading="h4" />
      </div>
    </section>
  );
}
