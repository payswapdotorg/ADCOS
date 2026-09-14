"use client";

/**
 * FirstRunCard — the V2 product-education surface for the fresh/
 * disconnected/connected-empty home states (the frozen V2 design §5,
 * §13, §15; plan Task 4).
 *
 * The DEC-0128 program, Tasks 4-5 wave, Task 4 of the frozen plan. This
 * card REPLACES the V1 procedural three-step starter: the first surface
 * a disconnected visitor sees teaches the product, not the procedure —
 *
 * - "What ADCOS does" — the frozen design §5 anchor sentence VERBATIM;
 * - the mental model as a CLICKABLE lifecycle (§5): Describe requirement
 *   → Eligibility → Plan → Fulfillment → Assurance → Continuous
 *   fulfillment — each stage a 44px-target chip that opens the stage's
 *   concept education in the ConceptExplainer DRAWER (the stage's what/
 *   why/what-ADCOS-does/objects/operations all come from the REAL W1
 *   education registry — nothing is re-authored here);
 * - the "one connectivity contract, many networks, continuous
 *   fulfillment" line made visual WITHOUT inventing topology: the
 *   CONTRACT sits at the center and fulfillment renders as continuous
 *   work — no provider graph (provider-owned topology rule);
 * - the eight "I want to…" goal paths (§13), each linking to a REAL
 *   destination — no dead ends;
 * - the obvious next action per state: Quickstart when disconnected,
 *   "create your first contract" when connected-and-empty.
 *
 * Truth rules (§17): when the runtime reports degraded coordination
 * (readyz ok=false, or the readiness read itself failed) the card says
 * so with the V1 system-health vocabulary — the education describes the
 * product, never the current runtime state.
 *
 * Provenance of strings: the anchor sentence and the lifecycle/goal
 * labels are the frozen design's own product language (§5/§13); every
 * EDUCATION string (definitions, why-it-matters, related objects and
 * operations) is rendered from `@/lib/education` through the W1
 * learning primitives — never re-implemented here.
 */

import type { ReactNode } from "react";
import Link from "next/link";
import type { Readiness } from "@/lib/api/types";
import { ConceptExplainer } from "@/features/learning";
import { AlertIcon } from "@/components/ui";
import { cn } from "@/lib/utils";

/** Stable test id for the whole education surface. */
export const FIRST_RUN_TEST_ID = "first-run-education";

/** Stable test id for the verbatim §5 anchor sentence. */
export const FIRST_RUN_ANCHOR_TEST_ID = "first-run-anchor";

/** Stable test id for the honest degraded note. */
export const FIRST_RUN_DEGRADED_TEST_ID = "first-run-degraded";

/** Stable test id for the connected-empty first-contract path. */
export const FIRST_CONTRACT_PATH_TEST_ID = "first-contract-path";

/** Stable test id for one lifecycle stage chip. */
export const LIFECYCLE_STAGE_TEST_ID = "lifecycle-stage";

/** Stable test id for one goal path. */
export const GOAL_PATH_TEST_ID = "goal-path";

/**
 * The frozen design §5 anchor sentence — VERBATIM, the first thing a
 * disconnected visitor reads.
 */
export const ADCOS_ANCHOR_SENTENCE =
  "ADCOS lets an application describe the connectivity it needs as a durable contract and continuously works to fulfill that contract across available connectivity capabilities.";

/**
 * The mental-model lifecycle (frozen design §5, verbatim stage names),
 * each stage bound to its concept in the W1 education registry. The
 * stage's explanation — what it means, why it exists, what ADCOS
 * actually does, the relevant object, the relevant API operations — is
 * the registry's own record, rendered by ConceptExplainer.
 */
export const LIFECYCLE_STAGES: { stage: string; conceptId: string }[] = [
  { stage: "Describe requirement", conceptId: "connectivity-contract" },
  { stage: "Eligibility", conceptId: "eligibility" },
  { stage: "Plan", conceptId: "execution-plan" },
  { stage: "Fulfillment", conceptId: "fulfillment" },
  { stage: "Assurance", conceptId: "assurance" },
  { stage: "Continuous fulfillment", conceptId: "replan-failover" },
];

/**
 * The eight "I want to…" goal paths (frozen design §13, verbatim goal
 * names) with their REAL destinations — every href is an existing
 * console/docs route; "Understand my connectivity" and "Diagnose a
 * failure" carry a second destination because both honestly have two.
 */
export const GOAL_PATHS: {
  goal: string;
  description: string;
  href: string;
  extra?: { label: string; href: string };
}[] = [
  {
    goal: "Get connectivity",
    description:
      "The guided nine-step journey — a real contract lifecycle, start to evidence.",
    href: "/quickstart",
  },
  {
    goal: "Understand my connectivity",
    description:
      "What ADCOS is and what the connectivity contract actually says.",
    href: "/docs/start/what-is-adcos",
    extra: {
      label: "The connectivity contract concept",
      href: "/docs/concepts/connectivity-contract",
    },
  },
  {
    goal: "Connect my application",
    description:
      "The Developers workspace — connect an application credential (in memory only).",
    href: "/developers",
  },
  {
    goal: "Integrate the API",
    description: "Every operation of the accepted boundary, with education.",
    href: "/docs/api",
  },
  {
    goal: "Monitor fulfillment",
    description:
      "The Fulfillment workspace — execution status and demonstration runs.",
    href: "/fulfillment",
  },
  {
    goal: "Understand a decision",
    description:
      "The contracts workspace — eligibility and lifecycle reasoning per contract.",
    href: "/connectivity",
  },
  {
    goal: "Diagnose a failure",
    description: "The error workbench and the troubleshooting guide.",
    href: "/settings/errors",
    extra: { label: "Troubleshooting", href: "/docs/troubleshooting" },
  },
  {
    goal: "Add or integrate a provider",
    description: "The provider-adapter integration guide.",
    href: "/docs/guides/integrate-provider-adapter",
  },
];

/** The §15 section heading treatment (strong editorial hierarchy). */
function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
      {children}
    </h2>
  );
}

/**
 * One lifecycle stage chip — the ConceptExplainer drawer with a custom
 * trigger (the ConceptLink chip convention: 44px target pill, the
 * accessible name carries the stage's registry term, focus returns to
 * the chip when the drawer closes).
 */
function LifecycleStageChip({ stage, conceptId }: { stage: string; conceptId: string }) {
  return (
    <ConceptExplainer
      id={conceptId}
      mode="drawer"
      trigger={({ ref, open, onToggle }) => (
        <button
          ref={ref}
          type="button"
          data-testid={LIFECYCLE_STAGE_TEST_ID}
          onClick={onToggle}
          aria-haspopup="dialog"
          aria-expanded={open}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface"
        >
          {stage}
          <span aria-hidden="true" className="text-ink-faint">
            ?
          </span>
        </button>
      )}
    />
  );
}

/**
 * The mental model made visual WITHOUT inventing topology: the
 * CONTRACT at the center, fulfillment as continuous work around it.
 * No provider nodes, no graph — provider-native topology stays
 * provider-owned (non-negotiable #4), and the caption says so.
 */
function ContractAtCenterModel() {
  return (
    <div
      data-testid="first-run-model"
      className="flex flex-col items-center gap-3 rounded-md border border-line bg-raised px-4 py-5"
    >
      <svg
        viewBox="0 0 220 120"
        role="img"
        aria-label="One connectivity contract at the center, with continuous fulfillment work around it — no provider topology is drawn, because provider topology stays provider-owned."
        className="w-full max-w-xs text-ink-faint"
      >
        {/* the continuous work — a dashed loop with an arrowhead */}
        <circle
          cx="110"
          cy="60"
          r="46"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeDasharray="4 5"
        />
        <path d="M 148 40 l 6 8 -10 2 z" fill="currentColor" />
        {/* the contract — the sole durable authority at the center */}
        <rect
          x="58"
          y="46"
          width="104"
          height="28"
          rx="6"
          className="fill-surface stroke-line-strong"
          strokeWidth="1.5"
        />
        <text
          x="110"
          y="64"
          textAnchor="middle"
          className="fill-ink font-mono"
          fontSize="9"
        >
          Connectivity contract
        </text>
        {/* the loop's own label */}
        <text x="110" y="16" textAnchor="middle" className="fill-ink-faint font-mono" fontSize="8">
          continuous fulfillment work
        </text>
      </svg>
      <div className="flex flex-col items-center gap-1 text-center">
        <p className="text-sm font-medium text-ink">
          One connectivity contract, many networks, continuous fulfillment.
        </p>
        <p className="max-w-md text-xs leading-relaxed text-ink-faint">
          ADCOS composes available provider capabilities to keep fulfilling
          the one contract. Provider-native topology, routing and subscriber
          authority stay with the provider — the console never draws a
          provider graph.
        </p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * The card
 * ------------------------------------------------------------------ */

export function FirstRunCard({
  connected,
  hasContracts,
  readiness,
  readinessError,
  className,
}: {
  /** True when a session is connected (the connected-empty case shows
   * the first-contract path instead of the connect guidance). */
  connected: boolean;
  /** True once the contracts list has loaded AND carries at least one
   * contract — the caller never mounts this card in that state, but the
   * prop keeps the card honest if composition changes. */
  hasContracts: boolean;
  /** The platform readiness payload (GET /readyz), when loaded. */
  readiness: Readiness | null;
  /** The readiness read's error, when the read itself failed. */
  readinessError: unknown;
  className?: string;
}) {
  // §17: the education must not lie about the runtime — degraded
  // coordination is shown with the V1 system-health vocabulary.
  const degraded =
    readinessError !== null && readinessError !== undefined
      ? true
      : readiness !== null && readiness.ok === false;
  const connectedEmpty = connected && !hasContracts;

  return (
    <section
      data-testid={FIRST_RUN_TEST_ID}
      aria-label="What ADCOS does"
      className={cn(
        "flex flex-col gap-6 rounded-md border border-line bg-surface px-6 py-6",
        className,
      )}
    >
      {/* What ADCOS does — the frozen §5 anchor sentence, verbatim */}
      <div className="flex flex-col gap-2">
        <SectionHeading>What ADCOS does</SectionHeading>
        <p
          data-testid={FIRST_RUN_ANCHOR_TEST_ID}
          className="max-w-3xl text-lg leading-relaxed text-ink"
        >
          {ADCOS_ANCHOR_SENTENCE}
        </p>
      </div>

      {/* The degraded note — honest, V1 vocabulary, before the education */}
      {degraded ? (
        <p
          data-testid={FIRST_RUN_DEGRADED_TEST_ID}
          role="note"
          className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/5 px-3 py-2 text-sm leading-relaxed text-ink-muted"
        >
          <AlertIcon size={14} className="mt-0.5 shrink-0 text-warning" />
          <span>
            <span className="font-medium text-ink">degraded readiness</span>{" "}
            — the runtime reports degraded coordination right now. This page
            describes the product, not the current runtime state: open{" "}
            <a
              href="#home-system-health"
              className="text-accent transition-colors hover:text-ink"
            >
              System health
            </a>{" "}
            below for the backends&apos; own states and details.
          </span>
        </p>
      ) : null}

      {/* The mental model as a clickable lifecycle */}
      <div className="flex flex-col gap-2.5">
        <SectionHeading>The mental model — click any stage</SectionHeading>
        <ol
          aria-label="The ADCOS lifecycle"
          className="flex flex-wrap items-center gap-1.5"
        >
          {LIFECYCLE_STAGES.map((item, index) => (
            <li key={item.stage} className="flex items-center gap-1.5">
              {index > 0 ? (
                <span aria-hidden="true" className="shrink-0 text-ink-faint">
                  →
                </span>
              ) : null}
              <LifecycleStageChip
                stage={item.stage}
                conceptId={item.conceptId}
              />
            </li>
          ))}
        </ol>
        <p className="max-w-2xl text-xs leading-relaxed text-ink-faint">
          Every stage opens its own explanation — what it means, why it
          exists, what ADCOS actually does, the relevant object and the
          relevant API operations.
        </p>
      </div>

      {/* One contract, many networks, continuous fulfillment — visual */}
      <div className="flex flex-col gap-2.5">
        <SectionHeading>
          One contract, many networks, continuous fulfillment
        </SectionHeading>
        <ContractAtCenterModel />
      </div>

      {/* The eight goal paths */}
      <div className="flex flex-col gap-2.5">
        <SectionHeading>I want to…</SectionHeading>
        <ul className="grid gap-2 sm:grid-cols-2">
          {GOAL_PATHS.map((path) => (
            <li key={path.goal} data-testid={GOAL_PATH_TEST_ID}>
              <Link
                href={path.href}
                className="flex h-full flex-col gap-1 rounded-md border border-line bg-raised px-3 py-2.5 transition-colors hover:border-line-strong hover:bg-surface"
              >
                <span className="text-sm font-medium text-ink">
                  {path.goal}
                </span>
                <span className="text-xs leading-relaxed text-ink-muted">
                  {path.description}
                </span>
              </Link>
              {path.extra ? (
                <Link
                  href={path.extra.href}
                  className="mt-1 inline-flex text-xs text-accent transition-colors hover:text-ink"
                >
                  {path.extra.label} →
                </Link>
              ) : null}
            </li>
          ))}
        </ul>
      </div>

      {/* The obvious next action — never a dead end */}
      <div className="flex flex-col gap-2.5">
        <SectionHeading>Next</SectionHeading>
        {connectedEmpty ? (
          <div
            data-testid={FIRST_CONTRACT_PATH_TEST_ID}
            className="flex flex-col gap-2"
          >
            <p className="text-sm leading-relaxed text-ink-muted">
              This session is connected and no contracts exist yet — record
              your first connectivity intent and follow it through the
              lifecycle.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href="/connectivity"
                className="inline-flex min-h-11 items-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-ink transition-colors hover:bg-accent-strong"
              >
                Create your first contract
                <span aria-hidden="true">→</span>
              </Link>
              <Link
                href="/quickstart"
                className="inline-flex min-h-11 items-center rounded-md border border-line-strong bg-raised px-4 text-sm text-ink transition-colors hover:bg-surface"
              >
                Take the guided Quickstart
              </Link>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <p className="text-sm leading-relaxed text-ink-muted">
              No session is connected. Connect an application with the
              session menu (top right — the credential lives in memory
              only), or start the guided Quickstart now: it works end to
              end in the deterministic demo context, no credential needed.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href="/quickstart"
                className="inline-flex min-h-11 items-center gap-2 rounded-md bg-accent px-4 text-sm font-medium text-accent-ink transition-colors hover:bg-accent-strong"
              >
                Start the Quickstart
                <span aria-hidden="true">→</span>
              </Link>
              <a
                href="#home-demo"
                className="inline-flex min-h-11 items-center rounded-md border border-line-strong bg-raised px-4 text-sm text-ink transition-colors hover:bg-surface"
              >
                Run the fulfillment demonstration
              </a>
              <Link
                href="/tour"
                className="inline-flex min-h-11 items-center rounded-md border border-line-strong bg-raised px-4 text-sm text-ink transition-colors hover:bg-surface"
              >
                The interactive tour
              </Link>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
