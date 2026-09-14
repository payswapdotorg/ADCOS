/**
 * SdkPage — the SDKs page of the docs IA, HONEST by construction (the
 * frozen V2 design §9/§17 and the plan's non-goal "no invented
 * SDKs"): no ADCOS SDK exists today, and this page says so instead of
 * presenting dead downloads or fabricated package names.
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan. What it DOES document is real: the API-first
 * surface (the coverage registry's 25 operations), the console's own
 * typed browser client as the reference implementation of that
 * surface, and curl as the reproducible path (the request inspector
 * emits it from real console requests). When an SDK exists, it will
 * appear here — nothing on this page invents one.
 */

import Link from "next/link";
import { COVERAGE, developerOperations } from "@/lib/api/coverage";
import { DocsLink, DocsPageFrame, DocsSection } from "./docs-shared";

/** Stable test id for the SDK disclosure block. */
export const SDK_PAGE_TEST_IDS = {
  root: "docs-sdk-page",
  disclosure: "docs-sdk-disclosure",
} as const;

/** The honest disclosure — the page's primary statement. */
export const SDK_DISCLOSURE =
  "No ADCOS SDK exists today — not for this console, not for any language.";

export function SdkPage() {
  return (
    <DocsPageFrame
      sectionId="sdk"
      pageLabel="SDKs"
      title="SDKs"
      lede="The honest state of software development kits for the ADCOS API — and the surfaces you can build against today."
    >
      <div
        data-testid={SDK_PAGE_TEST_IDS.disclosure}
        className="rounded-md border border-warning/60 bg-warning/5 px-4 py-3"
        role="note"
      >
        <p className="text-sm font-medium text-ink">{SDK_DISCLOSURE}</p>
        <p className="mt-1 text-sm leading-relaxed text-ink-muted">
          This page will list real SDKs when real SDKs exist. Until then it
          documents what is actually available — the API itself, the console&apos;s
          typed client as the reference implementation, and curl as the
          reproducible path. Nothing here fabricates a package, a version or a
          download.
        </p>
      </div>

      <DocsSection
        id="api-first"
        title="The API-first surface"
        description="What you integrate against today, in full."
      >
        <p className="text-sm leading-relaxed text-ink-muted">
          ADCOS is API-first: the accepted HTTP boundary is the integration
          surface — {developerOperations().length} versioned, authenticated
          developer-API operations plus the platform routes, {COVERAGE.length}{" "}
          in all, every one documented on the{" "}
          <Link href="/docs/api" className="text-accent hover:underline">
            API documentation pages
          </Link>
          . Responses carry typed envelopes with request ids, rate-limit
          surfaces and idempotency information; mutations require an
          idempotency key; errors carry the backend&apos;s canonical reason codes
          verbatim.
        </p>
      </DocsSection>

      <DocsSection
        id="reference-implementation"
        title="The typed client — the reference implementation"
        description="The console's own browser client (web/src/lib/api/client.ts) — not a distributable SDK."
      >
        <p className="text-sm leading-relaxed text-ink-muted">
          This console talks to the boundary through a typed TypeScript client
          — the same client the API Explorer executes with. It is the
          reference implementation of the surface: one function per coverage
          operation, the envelope types, the verbatim reason-code error type,
          automatic idempotency keys on mutations. It ships inside the console
          rather than as a package, and it is browser-side code — but its
          request shapes are exactly the shapes any integration sends.
        </p>
        <p className="text-sm leading-relaxed text-ink-muted">
          The fastest way to see the exact requests: the{" "}
          <DocsLink
            link={{ kind: "route", id: "/developers/requests", label: "request inspector" }}
          />{" "}
          captures every console-made request with its reproducible curl.
        </p>
      </DocsSection>

      <DocsSection
        id="curl"
        title="curl — the reproducible path"
        description="Reproduce any console action as a plain HTTP request."
      >
        <p className="text-sm leading-relaxed text-ink-muted">
          Every operation page documents the real method, path, capability and
          example body, and the request inspector emits the curl for requests
          the console actually made — the honest bridge between clicking in
          the console and writing your integration&apos;s code.
        </p>
        <p className="text-sm leading-relaxed text-ink-muted">
          The step-by-step integration path is the{" "}
          <DocsLink
            link={{
              kind: "guide",
              id: "integrate-adcos-api",
              label: "Integrate the ADCOS API playbook",
            }}
          />
          .
        </p>
      </DocsSection>
    </DocsPageFrame>
  );
}
