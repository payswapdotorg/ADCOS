/**
 * ErrorsPage — the canonical reason codes of the ADCOS boundary,
 * rendered VERBATIM with human guidance (the frozen V2 design §3
 * non-negotiable 7: teaching layers may explain the codes but never
 * replace them).
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan. The code list below is the FROZEN PIN of the
 * canonical vocabulary — transcribed verbatim from the REASON_PRESENTATION
 * map of `@/lib/api/errors` (the same pin tests/education-registry.test.ts
 * carries; the module keeps the map private) — and every code's
 * PRESENTATION (title / next action) is derived at render time through
 * the canonical `describeError` API itself, so the guidance text comes
 * from the errors module and never from this page. A module-load guard
 * fails loudly if the pin ever duplicates or drifts in size. Unknown
 * codes stay unknown: the console shows them verbatim without invented
 * semantics — the honest fallback, stated below.
 */

import Link from "next/link";
import { AdcosApiError, describeError, type ErrorPresentation } from "@/lib/api/errors";
import { DocsPageFrame, DocsSection } from "./docs-shared";

/** Stable test ids for the errors page. */
export const DOCS_ERRORS_TEST_IDS = {
  root: "docs-errors-page",
  family: "docs-error-family",
  code: "docs-error-code",
} as const;

/** The exact expected size of the pinned vocabulary (the load guard). */
const EXPECTED_REASON_CODE_COUNT = 32;

/**
 * The canonical reason-code vocabulary, transcribed VERBATIM from
 * `@/lib/api/errors` (its private REASON_PRESENTATION map — the only
 * error vocabulary the console displays). Family grouping is this
 * page's own presentation choice; the codes themselves are canonical.
 */
const REASON_CODE_FAMILIES: { id: string; label: string; intro: string; codes: string[] }[] = [
  {
    id: "authentication-capability",
    label: "Authentication & capability",
    intro:
      "Who is calling, and what that application is allowed to do. Credentials follow backend issuance and reveal rules; capability grants unlock operations.",
    codes: [
      "authentication-invalid",
      "authentication-expired",
      "environment-mismatch",
      "capability-denied",
    ],
  },
  {
    id: "request-shape",
    label: "Request shape & transport",
    intro:
      "How the request itself must look: the versioned route, the JSON body, frozen vocabularies, size and rate limits.",
    codes: [
      "version-unsupported",
      "rate-limited",
      "payload-too-large",
      "malformed-json",
      "invalid-request-body",
      "invalid-input",
      "temporal-invalid",
      "secret-rejected",
      "vocabulary",
    ],
  },
  {
    id: "routing-resources",
    label: "Routing & resources",
    intro:
      "Whether the route exists on the accepted boundary and the resource exists — and is visible to this application.",
    codes: ["route-unknown", "resource-unknown", "unknown-contract"],
  },
  {
    id: "state-machine",
    label: "Contract & object state machine",
    intro:
      "Whether the object's current state permits the command. Contracts, offers, activations and leases move through a frozen state machine; hard constraints are immutable after creation.",
    codes: [
      "invalid-transition",
      "invalid-state",
      "contract-terminal",
      "constraint-immutable",
      "not-yet-valid",
      "expired",
      "sequence-conflict",
      "replay-stale",
    ],
  },
  {
    id: "pagination-filters",
    label: "Pagination & filters",
    intro: "List-request parameters: cursors, limits and the declared filter members.",
    codes: ["pagination-invalid", "filter-invalid"],
  },
  {
    id: "idempotency",
    label: "Idempotency",
    intro:
      "Mutation replay semantics: mutations require an idempotency key, and a key reused with a different body is a conflict, not a silent success.",
    codes: ["idempotency-key-required", "idempotency-conflict"],
  },
  {
    id: "runtime-durability",
    label: "Runtime & durability",
    intro:
      "The platform's own health: reachability, the runtime's unexpected failures, and the durable store and journal underneath it.",
    codes: ["backend-unreachable", "internal-error", "store-failed", "journal-tamper"],
  },
];

/**
 * The client-side-synthesized codes (mirroring `@/lib/api/errors`' own
 * labeling): `backend-unreachable` is what the typed client reports when
 * a request never reached the runtime; `internal-error` is the
 * runtime-level envelope's code. Both still render verbatim.
 */
const CLIENT_SYNTHESIZED_CODES = new Set(["backend-unreachable"]);

/* The module-load guard: the pin must be exactly the canonical size, with no duplication. */
{
  const all = REASON_CODE_FAMILIES.flatMap((family) => family.codes);
  if (new Set(all).size !== all.length) {
    throw new Error("docs errors page: the pinned reason-code vocabulary has a duplicate");
  }
  if (all.length !== EXPECTED_REASON_CODE_COUNT) {
    throw new Error(
      `docs errors page: the pinned reason-code vocabulary has ${all.length} codes, expected ${EXPECTED_REASON_CODE_COUNT}`,
    );
  }
}

/** The canonical presentation for one code — derived through describeError itself. */
function presentationFor(code: string): ErrorPresentation {
  return describeError(
    new AdcosApiError({
      status: 400,
      reason: code,
      message: "",
      request: { method: "GET", path: "(documentation)" },
    }),
  );
}

function ReasonCodeRow({ code }: { code: string }) {
  const presentation = presentationFor(code);
  const synthesized = CLIENT_SYNTHESIZED_CODES.has(code);
  return (
    <li id={`code-${code}`} data-testid={DOCS_ERRORS_TEST_IDS.code} data-code={code}>
      <div className="flex flex-col gap-1 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <code className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink">
            {presentation.reasonCode}
          </code>
          <span className="text-sm font-medium text-ink">{presentation.title}</span>
          {synthesized ? (
            <span className="rounded border border-line px-1.5 py-px font-mono text-2xs text-ink-faint">
              synthesized client-side
            </span>
          ) : null}
        </div>
        <p className="text-sm leading-relaxed text-ink-muted">
          <span className="text-ink-faint">Next:</span> {presentation.nextAction}
        </p>
      </div>
    </li>
  );
}

export function ErrorsPage() {
  const familyCount = REASON_CODE_FAMILIES.length;
  return (
    <DocsPageFrame
      sectionId="errors"
      pageLabel="Errors"
      title="Errors"
      lede={
        <>
          The backend&apos;s reason codes are the only error vocabulary the console
          displays — {EXPECTED_REASON_CODE_COUNT} canonical codes in{" "}
          {familyCount} families, rendered verbatim with the guidance that
          explains them. Guidance may add context; it never replaces the code.
        </>
      }
      wide
    >
      <DocsSection
        id="how-errors-read"
        title="How to read an ADCOS error"
        description="The typed envelope: reason, message, request id, retryability — and what the console does with it."
      >
        <ul className="flex flex-col gap-2 text-sm leading-relaxed text-ink-muted">
          <li>
            <strong className="font-medium text-ink">The code is canonical.</strong>{" "}
            Every non-2xx response carries a reason code; the console displays
            it verbatim wherever an error appears, and so does this page.
          </li>
          <li>
            <strong className="font-medium text-ink">The guidance is presentation.</strong>{" "}
            The title and next action below come from the canonical error
            presentation module — they explain the code&apos;s meaning and the
            honest next move, without rewriting the code.
          </li>
          <li>
            <strong className="font-medium text-ink">Unknown codes stay unknown.</strong>{" "}
            If the backend ever sends a code outside this vocabulary, the
            console shows it verbatim with the honest generic fallback — never
            invented semantics.
          </li>
          <li>
            <strong className="font-medium text-ink">See them live.</strong> The{" "}
            <Link href="/settings/errors" className="text-accent hover:underline">
              error workbench
            </Link>{" "}
            shows the full anatomy of every captured error, including the
            reproducible request.
          </li>
        </ul>
      </DocsSection>

      {REASON_CODE_FAMILIES.map((family) => (
        <section
          key={family.id}
          id={`family-${family.id}`}
          data-testid={DOCS_ERRORS_TEST_IDS.family}
          data-family={family.id}
          aria-labelledby={`family-${family.id}-heading`}
        >
          <h2
            id={`family-${family.id}-heading`}
            className="text-2xs font-normal uppercase tracking-wide text-ink-faint"
          >
            {family.label}
            <span className="ml-2 font-mono normal-case">{family.codes.length}</span>
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-ink-muted">{family.intro}</p>
          <ul className="mt-2 flex flex-col divide-y divide-line rounded-md border border-line bg-surface">
            {family.codes.map((code) => (
              <ReasonCodeRow key={code} code={code} />
            ))}
          </ul>
        </section>
      ))}
    </DocsPageFrame>
  );
}

/** The full pinned vocabulary (flat), for callers that need the list. */
export const PINNED_REASON_CODES: readonly string[] = REASON_CODE_FAMILIES.flatMap(
  (family) => family.codes,
);
