/**
 * TroubleshootingPage — the Troubleshooting hub of the docs IA
 * (the frozen V2 design §9): curated diagnosis paths for the four
 * canonical trouble classes — connect failures, the 404 route-unknown,
 * degraded coordination, and the absence of replan events — each
 * linking to the related concepts, guides, operations and reason codes.
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan. Every diagnosis path is composed from REAL console
 * surfaces and the registry vocabulary; where the current deployment
 * does not expose a capability, the §17 truth-and-disclosure pattern
 * states the actual state instead of implying it (the replan-events
 * disclosure is stated verbatim).
 */

import Link from "next/link";
import type { ReactNode } from "react";
import { DocsLink, DocsPageFrame, DocsSection } from "./docs-shared";

/** Stable test id for the troubleshooting hub. */
export const TROUBLESHOOTING_PAGE_TEST_IDS = {
  root: "docs-troubleshooting-page",
  topic: "docs-troubleshooting-topic",
} as const;

/** The §17 disclosure for the replanning capability — stated verbatim. */
export const REPLAN_EVENTS_NOT_EXPOSED =
  "Replan events are not currently exposed by this deployment. The backend capability exists in the architecture, but this console cannot inspect live replan events until the HTTP surface exposes them.";

/** An operation link labeled with the backend's own operation id (mono). */
function opLink(operationId: string) {
  return { kind: "operation" as const, id: operationId, label: operationId };
}

/** A mono reason-code chip linking to its Errors-page anchor. */
function ReasonCodeLink({ code }: { code: string }) {
  return (
    <Link
      href={`/docs/errors#code-${code}`}
      className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted transition-colors hover:border-line-strong hover:text-ink"
    >
      {code}
    </Link>
  );
}

interface TroubleshootingTopic {
  id: string;
  title: string;
  symptom: ReactNode;
  why: ReactNode;
  actions: ReactNode;
}

const TROUBLESHOOTING_TOPICS: TroubleshootingTopic[] = [
  {
    id: "cannot-connect",
    title: "The console cannot connect",
    symptom: (
      <>
        Connecting an application fails, or every request fails with{" "}
        <ReasonCodeLink code="backend-unreachable" /> — the shell&apos;s
        environment indicator reports the runtime unreachable or degraded.
      </>
    ),
    why: (
      <>
        Credentials are issued per environment and expire (
        <ReasonCodeLink code="authentication-invalid" />,{" "}
        <ReasonCodeLink code="authentication-expired" />,{" "}
        <ReasonCodeLink code="environment-mismatch" />
        ); and the console reaches the runtime same-origin only — if the
        runtime is down, requests never leave (
        <ReasonCodeLink code="backend-unreachable" /> is synthesized by the
        typed client, clearly labeled as such).
      </>
    ),
    actions: (
      <>
        Check the application id and credential in the session menu, then
        reconnect. Check the runtime itself: <DocsLink link={opLink("readyz")} />{" "}
        reports every consumed backend&apos;s state (the shell polls it;{" "}
        <Link href="/settings" className="text-accent hover:underline">
          Settings
        </Link>{" "}
        shows the full document). Then read{" "}
        <DocsLink
          link={{ kind: "concept", id: "application-capability", label: "Application and capability" }}
        />{" "}
        for the identity/capability model, or the{" "}
        <DocsLink
          link={{ kind: "guide", id: "integrate-adcos-api", label: "Integrate the ADCOS API playbook" }}
        />
        .
      </>
    ),
  },
  {
    id: "route-unknown",
    title: "A request returns 404 route-unknown",
    symptom: (
      <>
        A typed 404 envelope whose reason is{" "}
        <ReasonCodeLink code="route-unknown" /> — the console requested a
        route the runtime does not expose.
      </>
    ),
    why: (
      <>
        The accepted boundary is a fixed route table: exactly the{" "}
        <Link href="/docs/api" className="text-accent hover:underline">
          25 documented operations
        </Link>
        . A route outside it does not exist (
        <ReasonCodeLink code="resource-unknown" /> and{" "}
        <ReasonCodeLink code="unknown-contract" /> are the resource-shaped
        siblings — the id does not exist, or is not visible to this
        application).
      </>
    ),
    actions: (
      <>
        The console only calls registry-backed routes — re-issue the request
        from the surface that made it, after a refresh. Verify the real method
        and path on the{" "}
        <Link href="/docs/api" className="text-accent hover:underline">
          API documentation pages
        </Link>
        , and inspect the exact request in the{" "}
        <Link href="/developers/requests" className="text-accent hover:underline">
          request inspector
        </Link>
        .
      </>
    ),
  },
  {
    id: "degraded-coordination",
    title: "Degraded coordination",
    symptom: (
      <>
        Contracts appear in the DEGRADED lifecycle state, or readiness reports
        a consumed backend degraded — sometimes both tell one story together.
      </>
    ),
    why: (
      <>
        DEGRADED is an honest lifecycle state, not a silent condition: the
        contract&apos;s connectivity is not currently being met as promised.
        Replanning — the explicit re-composition over the same hard
        constraints — is the architectural answer; see the honest limit below.
      </>
    ),
    actions: (
      <>
        Filter the contracts list by state (<DocsLink link={opLink("contracts_list")} />),
        read the honest lifecycle position with its statements (
        <DocsLink link={opLink("intent_lifecycle")} />
        ), and check the platform side (<DocsLink link={opLink("readyz")} />).
        If the contract should end, termination is the honest terminal
        command (<DocsLink link={opLink("contract_terminate")} />). The full
        path is the{" "}
        <DocsLink
          link={{ kind: "guide", id: "handle-degraded-connectivity", label: "Handle degraded connectivity playbook" }}
        />
        .
      </>
    ),
  },
  {
    id: "no-replan-events",
    title: "No visible replan events",
    symptom: (
      <>
        No replan decisions appear anywhere in the console — including the
        Replanning surface itself, which shows a clearly-labeled structure
        preview instead of events.
      </>
    ),
    why: <>{REPLAN_EVENTS_NOT_EXPOSED}</>,
    actions: (
      <>
        Read{" "}
        <DocsLink
          link={{ kind: "concept", id: "replan-failover", label: "Replan / failover" }}
        />{" "}
        for what a replan decision will carry (the trigger vocabulary, the
        re-composition, the reasoning and evidence), and the{" "}
        <Link href="/fulfillment/replan" className="text-accent hover:underline">
          Replanning surface
        </Link>{" "}
        for the honest current presentation. Degradation handling today is
        the{" "}
        <DocsLink
          link={{ kind: "guide", id: "handle-degraded-connectivity", label: "Handle degraded connectivity playbook" }}
        />
        .
      </>
    ),
  },
];

export function TroubleshootingPage() {
  return (
    <DocsPageFrame
      sectionId="troubleshooting"
      pageLabel="Troubleshooting"
      title="Troubleshooting"
      lede="Diagnosis paths for the canonical trouble classes. Every path starts from what you actually see, explains why, and ends on real console surfaces — never an invented cause."
    >
      {TROUBLESHOOTING_TOPICS.map((topic) => (
        <DocsSection key={topic.id} id={topic.id} title={topic.title}>
          <dl className="flex flex-col gap-3">
            <div>
              <dt className="text-xs text-ink-faint">What you see</dt>
              <dd className="mt-0.5 text-sm leading-relaxed text-ink-muted">{topic.symptom}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-faint">Why</dt>
              <dd className="mt-0.5 text-sm leading-relaxed text-ink-muted">{topic.why}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-faint">What to do</dt>
              <dd className="mt-0.5 text-sm leading-relaxed text-ink-muted">{topic.actions}</dd>
            </div>
          </dl>
        </DocsSection>
      ))}
      <DocsSection
        id="start-from-the-error"
        title="Start from the error itself"
        description="The verbatim reason code is the diagnosis anchor."
      >
        <p className="text-sm leading-relaxed text-ink-muted">
          Every captured error lands in the{" "}
          <Link href="/settings/errors" className="text-accent hover:underline">
            error workbench
          </Link>{" "}
          with its full anatomy — reason verbatim, message, request id, and
          the reproducible request. The{" "}
          <Link href="/docs/errors" className="text-accent hover:underline">
            Errors reference
          </Link>{" "}
          maps every canonical code to its guidance.
        </p>
      </DocsSection>
    </DocsPageFrame>
  );
}
