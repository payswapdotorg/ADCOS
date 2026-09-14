/**
 * StartPages — the curated Start here pages of the docs IA (the frozen
 * V2 design §9): the Start here hub, "What is ADCOS?", "How ADCOS
 * works" (the mental model lifecycle, stage by stage) and "First
 * connectivity contract" (the walkthrough, honest about the
 * demonstration context).
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan. These pages are CURATED (the only hand-written docs
 * prose); every ADCOS semantic they state is either the frozen design's
 * own product language (§5/§6) or comes from the Task-1 education
 * registry (`@/lib/education`), which the links resolve through.
 * Where the current deployment differs from the conceptual model, the
 * §17 truth-and-disclosure pattern states it plainly.
 */

import Link from "next/link";
import { ExternalLinkIcon } from "@/components/ui";
import { getConcept, getGuide, type LearningLink } from "@/lib/education";
import { DocsLink, DocsPageFrame, DocsSection } from "./docs-shared";

/* ------------------------------------------------------------------ *
 * Local link builders (labels resolved from the registries verbatim)
 * ------------------------------------------------------------------ */

/** An operation link labeled by the backend's own operation id. */
function opLink(operationId: string): LearningLink {
  return { kind: "operation", id: operationId, label: operationId };
}

/** A concept link labeled by the registry's own term. */
function conceptLink(conceptId: string): LearningLink {
  const concept = getConcept(conceptId);
  return { kind: "concept", id: conceptId, label: concept ? concept.term : conceptId };
}

/** A guide link labeled by the registry's own title. */
function guideLink(guideId: string): LearningLink {
  const guide = getGuide(guideId);
  return { kind: "guide", id: guideId, label: guide ? guide.title : guideId };
}

/** A calm inline list of DocsLinks. */
function LinkList({ links }: { links: LearningLink[] }) {
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      {links.map((link) => (
        <DocsLink key={`${link.kind}:${link.id}`} link={link} className="font-mono text-xs" />
      ))}
    </p>
  );
}

/** The Quickstart href — the route is the first-run wave's (plan Task 5). */
const QUICKSTART_HREF = "/quickstart";

/* ------------------------------------------------------------------ *
 * /docs/start — the Start here hub
 * ------------------------------------------------------------------ */

const START_PAGES = [
  {
    title: "What is ADCOS?",
    href: "/docs/start/what-is-adcos",
    description:
      "The product explanation — what ADCOS does, what it deliberately is not, and the mental model in one line.",
  },
  {
    title: "How ADCOS works",
    href: "/docs/start/how-it-works",
    description:
      "The mental model lifecycle explained stage by stage: describe requirement → eligibility → plan → fulfillment → assurance → continuous fulfillment.",
  },
  {
    title: "First connectivity contract",
    href: "/docs/start/first-contract",
    description:
      "The walkthrough of a first contract — from recording an intent to inspecting evidence, honest about the demonstration context.",
  },
];

export function StartHereHub() {
  return (
    <DocsPageFrame
      sectionId="start"
      title="Start here"
      lede="The three-page on-ramp to ADCOS: what it is, how it works, and your first connectivity contract. Read in order if the model is new to you — every later screen in the console becomes legible once the lifecycle is."
    >
      <ul className="flex flex-col divide-y divide-line rounded-md border border-line bg-surface">
        {START_PAGES.map((page) => (
          <li key={page.href}>
            <Link href={page.href} className="flex flex-col gap-1 px-4 py-3 transition-colors hover:bg-raised/40">
              <span className="text-sm font-medium text-accent">{page.title}</span>
              <span className="text-sm leading-relaxed text-ink-muted">{page.description}</span>
            </Link>
          </li>
        ))}
        <li>
          <Link href={QUICKSTART_HREF} className="flex flex-col gap-1 px-4 py-3 transition-colors hover:bg-raised/40">
            <span className="flex items-center gap-2 text-sm font-medium text-accent">
              Quickstart
              <ExternalLinkIcon size={10} className="text-ink-faint" />
            </span>
            <span className="text-sm leading-relaxed text-ink-muted">
              The guided first journey through a real contract lifecycle, step by step inside the console.
            </span>
          </Link>
        </li>
      </ul>
      <DocsSection title="Already past the basics?">
        <p className="text-sm leading-relaxed text-ink-muted">
          The <DocsLink link={{ kind: "docs", id: "concepts", label: "Concepts" }} /> pages
          answer the six questions for every first-class concept, the{" "}
          <DocsLink link={{ kind: "docs", id: "guides", label: "Guides" }} /> walk real
          playbooks, and the <DocsLink link={{ kind: "docs", id: "api", label: "API docs" }} />{" "}
          cover all 25 operations of the accepted boundary.
        </p>
      </DocsSection>
    </DocsPageFrame>
  );
}

/* ------------------------------------------------------------------ *
 * /docs/start/what-is-adcos — the product explanation (curated)
 * ------------------------------------------------------------------ */

export function WhatIsAdcosPage() {
  return (
    <DocsPageFrame
      sectionId="start"
      pageLabel="What is ADCOS?"
      title="What is ADCOS?"
      lede="The one-paragraph answer, what it means in practice, and what ADCOS deliberately is not."
    >
      <DocsSection id="the-answer" title="The one-paragraph answer">
        <p className="text-base leading-relaxed text-ink">
          ADCOS lets an application describe the connectivity it needs as a
          durable contract and continuously works to fulfill that contract
          across available connectivity capabilities.
        </p>
        <p className="text-sm leading-relaxed text-ink-muted">
          Three things follow from that sentence, and they are the whole
          product: <strong className="font-medium text-ink">you describe</strong>{" "}
          — the connectivity your application needs becomes a durable,
          canonical record instead of an ad-hoc request;{" "}
          <strong className="font-medium text-ink">ADCOS works</strong> — the
          system reasons about eligibility, composes an execution plan, and
          keeps fulfilling rather than provisioning once;{" "}
          <strong className="font-medium text-ink">across capabilities</strong>{" "}
          — provider capabilities are composed to meet the contract, and
          providers keep authority over their own networks.
        </p>
      </DocsSection>

      <DocsSection id="the-lifecycle" title="The mental model in one line">
        <p className="font-mono text-sm leading-relaxed text-ink">
          Describe requirement → Eligibility → Plan → Fulfillment → Assurance →
          Continuous fulfillment
        </p>
        <p className="text-sm leading-relaxed text-ink-muted">
          Every stage is explained on{" "}
          <Link href="/docs/start/how-it-works" className="text-accent hover:underline">
            How ADCOS works
          </Link>
          , and every stage has first-class concept documentation behind it —
          start with{" "}
          <DocsLink link={conceptLink("connectivity-contract")} />.
        </p>
      </DocsSection>

      <DocsSection id="what-it-is-not" title="What ADCOS deliberately is not">
        <ul className="flex flex-col gap-2 text-sm leading-relaxed text-ink-muted">
          <li>
            <strong className="font-medium text-ink">Not a network operator.</strong>{" "}
            Providers supply capabilities through adapters; ADCOS composes and
            contracts over them. There is no universal ADCOS topology graph —
            provider-native topology, routing and subscriber authority stay
            with the provider. See{" "}
            <DocsLink link={conceptLink("provider-adapter-boundary")} />.
          </li>
          <li>
            <strong className="font-medium text-ink">Not a fabrication.</strong>{" "}
            Claims are backed by records with an evidence class, and
            software-side evidence is always labeled as software-side. In this
            deployment, physical/network evidence is{" "}
            <span className="font-mono text-xs text-ink">
              NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT
            </span>{" "}
            — and none is fabricated. See{" "}
            <DocsLink link={conceptLink("evidence")} />.
          </li>
          <li>
            <strong className="font-medium text-ink">Not silently weakened.</strong>{" "}
            Hard constraints recorded in the contract are immutable after
            creation; plans and replans are verified against them, never
            around them. See{" "}
            <DocsLink link={conceptLink("connectivity-contract")} />.
          </li>
        </ul>
      </DocsSection>

      <DocsSection id="see-it-work" title="See it work, honestly">
        <p className="text-sm leading-relaxed text-ink-muted">
          The fastest way to watch the whole lifecycle run end to end is the{" "}
          <DocsLink link={conceptLink("demo-fulfillment-journey")} /> — one
          deterministic document carrying the boundary trace, contract, plan,
          execution and evidence for a given instant. It is a demonstration,
          not production telemetry: identical instant → identical document,
          SOFTWARE evidence class only.
        </p>
        <LinkList links={[opLink("demo_contract_fulfillment")]} />
      </DocsSection>

      <DocsSection id="where-next" title="Where to go next">
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <Link href="/docs/start/how-it-works" className="text-accent hover:underline">
            How ADCOS works
          </Link>
          <Link href={QUICKSTART_HREF} className="text-accent hover:underline">
            Quickstart
          </Link>
          <Link href="/docs/concepts" className="text-accent hover:underline">
            Concepts
          </Link>
          <Link href="/docs/api" className="text-accent hover:underline">
            API documentation
          </Link>
        </p>
      </DocsSection>
    </DocsPageFrame>
  );
}

/* ------------------------------------------------------------------ *
 * /docs/start/how-it-works — the mental model lifecycle (curated)
 * ------------------------------------------------------------------ */

interface LifecycleStage {
  id: string;
  title: string;
  means: string;
  why: string;
  adcosDoes: string;
  objects: string;
  operations: string[];
  concepts: string[];
}

const LIFECYCLE_STAGES: LifecycleStage[] = [
  {
    id: "describe-requirement",
    title: "Describe requirement",
    means:
      "You tell ADCOS the connectivity your application needs — as a durable contract: requirements, hard constraints, a validity window and termination rules.",
    why: "The ask becomes canonical and durable. ADCOS never improvises what to fulfill: the contract is the sole contract authority, and every later stage composes over it.",
    adcosDoes:
      "You record an intent with the canonical material; ADCOS keeps it verbatim — opaque typed references pass through unchanged, never re-interpreted. Hard constraints are immutable once recorded.",
    objects: "Contract",
    operations: ["intent_create", "intents_list", "intent_get"],
    concepts: ["connectivity-contract"],
  },
  {
    id: "eligibility",
    title: "Eligibility",
    means:
      "The reasoning for why the contract's flow state is what it is — which requirements, constraints and policies shaped the current position.",
    why: "System behavior is explained instead of guessed. The reasoning is the backend's own; the console presents it and never re-implements a policy engine in the browser.",
    adcosDoes:
      "The lifecycle observation reports the contract state, execution status, evidence class, physical-connectivity position and the backend's statements — verbatim. Provider eligibility decisions as a list are not exposed by this deployment; what is exposed lives per contract in that observation.",
    objects: "ContractLifecycle",
    operations: ["intent_lifecycle", "intent_get"],
    concepts: ["eligibility", "policy"],
  },
  {
    id: "plan",
    title: "Plan",
    means:
      "The composition of provider capabilities that fulfills an accepted contract — produced over the same canonical hard constraints, never weakening them.",
    why: "The plan is the recorded step between what you asked for and what actually happens. When you want to know what ADCOS is doing, the plan material is the core of the answer.",
    adcosDoes:
      "ADCOS composes provider capabilities into an execution plan and binds it onto the contract as opaque execution-scope and execution-artifact references. The deterministic demonstration exposes the full plan leg so the shape is inspectable end to end.",
    objects: "Contract, DemoDocument",
    operations: ["contract_get", "intent_get", "demo_contract_fulfillment"],
    concepts: ["execution-plan", "provider-capability"],
  },
  {
    id: "fulfillment",
    title: "Fulfillment",
    means:
      "The continuous work of honoring an active contract: executing the plan, recording what happened, and keeping the obligation alive across the validity window.",
    why: "Continuously working to fulfill the contract is ADCOS's core promise — fulfillment is where that promise lives, observed rather than assumed.",
    adcosDoes:
      "The lifecycle observation reports an execution status per contract, and the deterministic demonstration exposes the execution leg in full. API success never claims physical connectivity — software-side transitions and evidence are labeled as such, and degraded or failed states are reported rather than hidden.",
    objects: "ContractLifecycle, DemoDocument",
    operations: ["intent_lifecycle", "demo_contract_fulfillment"],
    concepts: ["fulfillment"],
  },
  {
    id: "assurance",
    title: "Assurance",
    means:
      "The obligations a contract references — what must hold for the connectivity to count as assured, carried as referenced material.",
    why: "Assurance is the difference between connectivity having existed once and connectivity being maintained as promised.",
    adcosDoes:
      "The obligations are referenced, never evaluated in the console: assurance reads return them verbatim with the contract state and the backend's honest note. No attestation or evaluation operation exists on the accepted boundary — assurance reads are the exposed surface.",
    objects: "ContractAssurance",
    operations: ["contract_assurance"],
    concepts: ["assurance"],
  },
  {
    id: "continuous-fulfillment",
    title: "Continuous fulfillment",
    means:
      "The contract stays fulfilled across its validity window: leases grant bounded access windows, degradation is a visible lifecycle state, and replanning re-composes the plan when conditions change.",
    why: "Connectivity is an ongoing obligation, not a one-time setup — the contract keeps working until it is terminated or expires.",
    adcosDoes:
      "Leases are granted, renewed and revoked over the active contract; DEGRADED is reported with its statements, never hidden; termination is the honest terminal command. Replanning exists in the accepted architecture — see the honest limit below.",
    objects: "Contract, Lease",
    operations: ["contracts_list", "lease_grant", "lease_renew", "lease_revoke", "contract_terminate"],
    concepts: ["replan-failover", "fulfillment"],
  },
];

/** The §17 disclosure for the replanning capability — stated verbatim. */
export const REPLAN_EVENTS_DISCLOSURE =
  "Replan events are not currently exposed by this deployment. The backend capability exists in the architecture, but this console cannot inspect live replan events until the HTTP surface exposes them.";

export function HowAdcosWorksPage() {
  return (
    <DocsPageFrame
      sectionId="start"
      pageLabel="How ADCOS works"
      title="How ADCOS works"
      lede="The ADCOS mental model is one lifecycle. Each stage below explains what it means, why it exists, what ADCOS actually does, the relevant object and the API operations that expose it — with the documentation behind every term."
    >
      <p className="font-mono text-sm leading-relaxed text-ink">
        Describe requirement → Eligibility → Plan → Fulfillment → Assurance →
        Continuous fulfillment
      </p>
      {LIFECYCLE_STAGES.map((stage, index) => (
        <DocsSection
          key={stage.id}
          id={stage.id}
          title={`${index + 1}. ${stage.title}`}
        >
          <dl className="flex flex-col gap-3">
            <div>
              <dt className="text-xs text-ink-faint">What it means</dt>
              <dd className="mt-0.5 text-sm leading-relaxed text-ink">{stage.means}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-faint">Why it exists</dt>
              <dd className="mt-0.5 text-sm leading-relaxed text-ink-muted">{stage.why}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-faint">What ADCOS actually does</dt>
              <dd className="mt-0.5 text-sm leading-relaxed text-ink-muted">{stage.adcosDoes}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-faint">Relevant object</dt>
              <dd className="mt-0.5 font-mono text-xs text-ink-muted">{stage.objects}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-faint">Relevant API operations</dt>
              <dd className="mt-0.5">
                <LinkList links={stage.operations.map(opLink)} />
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-faint">Concept documentation</dt>
              <dd className="mt-0.5">
                <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                  {stage.concepts.map((conceptId) => (
                    <DocsLink
                      key={conceptId}
                      link={conceptLink(conceptId)}
                      className="text-sm"
                    />
                  ))}
                </p>
              </dd>
            </div>
          </dl>
        </DocsSection>
      ))}
      <DocsSection id="honest-limits" title="The honest limits of this deployment">
        <p className="text-sm leading-relaxed text-ink-muted">{REPLAN_EVENTS_DISCLOSURE}</p>
        <p className="text-sm leading-relaxed text-ink-muted">
          The same discipline applies to evidence: this deployment&apos;s
          evidence surface is the deterministic demonstration&apos;s records —
          all SOFTWARE class — and physical/network evidence is{" "}
          <span className="font-mono text-xs text-ink">NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT</span>.
          Nothing on any console screen implies otherwise.
        </p>
      </DocsSection>
      <DocsSection id="where-next" title="Where to go next">
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <Link href="/docs/start/first-contract" className="text-accent hover:underline">
            First connectivity contract
          </Link>
          <Link href={QUICKSTART_HREF} className="text-accent hover:underline">
            Quickstart
          </Link>
          <Link href="/docs/concepts" className="text-accent hover:underline">
            Concepts
          </Link>
          <DocsLink link={guideLink("first-connectivity-application")} />
        </p>
      </DocsSection>
    </DocsPageFrame>
  );
}

/* ------------------------------------------------------------------ *
 * /docs/start/first-contract — the walkthrough (curated, honest about
 * the demonstration context)
 * ------------------------------------------------------------------ */

interface WalkthroughStep {
  title: string;
  detail: string;
  links: LearningLink[];
}

const FIRST_CONTRACT_STEPS: WalkthroughStep[] = [
  {
    title: "Connect — or enter the supported demo context",
    detail:
      "Connect an issued application credential (the session menu, Developers workspace) to call the authenticated API, or use the deterministic demonstration as the supported demo context — it needs no authentication. Both are honest starting points.",
    links: [
      { kind: "route", id: "/developers", label: "The Developers workspace" },
      opLink("demo_contract_fulfillment"),
    ],
  },
  {
    title: "See your identity and capabilities",
    detail:
      "Every developer-API call runs as your application, and capability grants unlock operations. Check you hold intents:write before building — without it, mutations fail with capability-denied.",
    links: [opLink("application_self")],
  },
  {
    title: "Describe the connectivity you need",
    detail:
      "Record an intent: requirements, hard constraints (immutable once recorded), a validity window and termination rules. The builder in the contracts workspace composes the canonical body with you.",
    links: [
      opLink("intent_create"),
      { kind: "route", id: "/connectivity", label: "The contracts workspace" },
    ],
  },
  {
    title: "Review the canonical contract",
    detail:
      "Read the intent back. Every reference and constraint renders verbatim with its provenance — this is the material ADCOS will honor, and it is exactly what your integration will see.",
    links: [opLink("intent_get")],
  },
  {
    title: "Accept an offer",
    detail:
      "Accept the opaque typed offer references onto the intent — the contract moves to OFFER_SELECTED, the bridge from requirement to plan. This deployment exposes no offer catalog: offers enter through the API as canonical material and render verbatim.",
    links: [opLink("offers_accept")],
  },
  {
    title: "Activate",
    detail:
      "Activate the contract with the activation instant and signature references — the move to CONTRACT_ACTIVE, where fulfillment work begins.",
    links: [opLink("contract_activate")],
  },
  {
    title: "Observe the lifecycle",
    detail:
      "Read the lifecycle observation: contract state, execution status, evidence class and the backend's statements. Physical connectivity is never claimed by API success — the projection is honest software-side state.",
    links: [opLink("intent_lifecycle")],
  },
  {
    title: "Inspect evidence and assurance",
    detail:
      "The records behind the claims, and the obligations the contract references. In this deployment the demonstration's evidence records are all SOFTWARE class — honestly labeled, never re-badged.",
    links: [
      opLink("demo_contract_fulfillment"),
      opLink("contract_assurance"),
      { kind: "route", id: "/evidence", label: "The Evidence page" },
    ],
  },
  {
    title: "Reproduce through the API Explorer",
    detail:
      "Re-run any step as a real HTTP request and read the typed envelope, the headers and the verbatim reason codes — the same requests your integration will make.",
    links: [{ kind: "route", id: "/developers/explorer", label: "The API Explorer" }],
  },
];

export function FirstContractPage() {
  return (
    <DocsPageFrame
      sectionId="start"
      pageLabel="First connectivity contract"
      title="First connectivity contract"
      lede="The walkthrough of a first contract — the same path the Quickstart guides interactively: from recording an intent to inspecting the evidence behind it."
    >
      <DocsSection id="what-you-need" title="What you need">
        <ul className="flex flex-col gap-2 text-sm leading-relaxed text-ink-muted">
          <li>
            <strong className="font-medium text-ink">An issued application credential</strong>{" "}
            with the intents:write capability (leases and webhooks need their own grants) —
            see <DocsLink link={conceptLink("application-capability")} />; or
          </li>
          <li>
            <strong className="font-medium text-ink">The supported demo context</strong> — the
            deterministic demonstration, which needs no authentication. It is a
            demonstration, not production telemetry: SOFTWARE evidence class
            only, and no provider claim is made beyond the deterministic
            reference adapters.
          </li>
        </ul>
      </DocsSection>
      <ol className="flex flex-col gap-3">
        {FIRST_CONTRACT_STEPS.map((step, index) => (
          <li key={step.title}>
            <DocsSection title={`${index + 1}. ${step.title}`}>
              <p className="text-sm leading-relaxed text-ink-muted">{step.detail}</p>
              <LinkList links={step.links} />
            </DocsSection>
          </li>
        ))}
      </ol>
      <DocsSection id="next-paths" title="Next paths">
        <p className="text-sm leading-relaxed text-ink-muted">
          This walkthrough never fabricates a production capability: where the
          current deployment only supports the deterministic demonstration,
          the console says so. Continue with the guided version of this path,
          the full playbook, or the API surface:
        </p>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <Link href={QUICKSTART_HREF} className="text-accent hover:underline">
            Quickstart
          </Link>
          <DocsLink link={guideLink("first-connectivity-application")} />
          <Link href="/docs/api" className="text-accent hover:underline">
            API documentation
          </Link>
        </p>
      </DocsSection>
    </DocsPageFrame>
  );
}
