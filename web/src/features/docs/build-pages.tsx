/**
 * BuildPages — the "Build with ADCOS" documentation section (the frozen
 * Build-with-ADCOS design §8, plan Task 4): seven pages that teach how a
 * product fits ADCOS into its architecture.
 *
 *   /docs/build                      Choose an integration pattern (the hub)
 *   /docs/build/application          Pattern A — application integration
 *   /docs/build/gateway-relay        Pattern B — gateway / relay integration
 *                                    (THE ShareNet reference page, §13)
 *   /docs/build/fleet-subscriber     Pattern C — fleet / subscriber integration
 *   /docs/build/provider             Pattern D — provider integration
 *   /docs/build/lifecycle            Lifecycle implementation
 *   /docs/build/production-checklist Production checklist
 *
 * The pattern facts (ownership, operations, webhooks, failure behavior,
 * anti-patterns) are GENERATED from the integration registry
 * (`@/lib/integration`), which itself references the accepted coverage
 * registry (`@/lib/api/coverage`) — never a second endpoint catalog. The
 * prose is curated and follows the design's truth rules: webhooks are
 * observations, API success is never physical connectivity success,
 * software and physical/network evidence stay distinct, provider SDK
 * types never appear in application-facing examples, and the ShareNet
 * boundary (design §13) is stated exactly.
 */

import Link from "next/link";
import type { ComponentType, ReactNode } from "react";
import { EmptyState, ExternalLinkIcon } from "@/components/ui";
import { coverageByOperation, type CoverageRecord } from "@/lib/api/coverage";
import { getConcept, type LearningLink } from "@/lib/education";
import {
  INTEGRATION_PATTERNS,
  integrationPatternById,
  type IntegrationPattern,
} from "@/lib/integration";
import { DocsLink, DocsPageFrame, DocsSection, type DocsSectionMeta } from "./docs-shared";

/** Stable test ids for the build docs pages. */
export const BUILD_PAGE_TEST_IDS = {
  root: "docs-build-page",
  patternRow: "docs-build-pattern-row",
  unknown: "docs-build-unknown",
} as const;

/* ------------------------------------------------------------------ *
 * The section metadata (the docs home lists this between Guides and
 * API — design §8 ordering; DOCS_SECTIONS itself is owned by
 * docs-shared, so this feature composes its own section entry).
 * ------------------------------------------------------------------ */

export const BUILD_DOCS_SECTION: DocsSectionMeta = {
  id: "build",
  label: "Build with ADCOS",
  href: "/docs/build",
  description:
    "Choose an integration pattern, design the application/ADCOS/provider boundary, and take the production checklist.",
};

/** The ShareNet boundary teaching (design §13) — stated exactly. */
export const SHARENET_APPLICATION_AUTHORITY =
  "ShareNet keeps authority over content, P2P distribution, publisher trust, delivery receipts and application economics.";
export const SHARENET_ADCOS_AUTHORITY =
  "ADCOS manages technology-neutral gateway/relay connectivity contracts and fulfillment.";
export const SHARENET_PROVIDER_AUTHORITY = "Providers own provider-native realization.";
export const SHARENET_P2P_TRANSFER_RULE =
  "Ordinary device-to-device content transfers stay in ShareNet's data plane — they never become ADCOS connectivity transactions merely because gateway or backhaul connectivity uses ADCOS.";
export const SHARENET_OFFLINE_RULE =
  "ShareNet's local/P2P data plane operates independently when ADCOS is unreachable.";

/* ------------------------------------------------------------------ *
 * Local helpers (labels resolved from the registries verbatim)
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

/** A calm inline list of operation links (mono, like the docs pages). */
function OpList({ operationIds }: { operationIds: string[] }) {
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      {operationIds.map((operationId) => (
        <DocsLink
          key={operationId}
          link={opLink(operationId)}
          className="font-mono text-xs"
          showGlyph={false}
        />
      ))}
    </p>
  );
}

/** The webhook surface every pattern can use (real coverage operations). */
const WEBHOOK_OPERATION_IDS = ["endpoint_register", "endpoints_list", "deliveries_list"].filter(
  (operationId) => coverageByOperation(operationId) !== undefined,
);

/** The honest evidence statement shared by the pattern pages. */
const EVIDENCE_NOTE =
  "Lifecycle observations report contract state, execution status and evidence class; in this deployment the deterministic demonstration's records are all SOFTWARE class, and physical/network evidence is NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT — none is fabricated. Software evidence never proves physical or network connectivity.";

/** The shared return-path block: back to the section, forward to /build. */
function BuildWhereNext({ patternId }: { patternId?: string }) {
  return (
    <DocsSection id="where-next" title="Where next">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        <Link href="/docs/build" className="text-accent hover:underline">
          Build with ADCOS
        </Link>
        {patternId ? (
          <Link href={`/build?pattern=${patternId}`} className="text-accent hover:underline">
            Design this pattern in the console
            <ExternalLinkIcon size={10} className="ml-1 inline-block align-baseline" />
          </Link>
        ) : (
          <Link href="/build" className="text-accent hover:underline">
            Design an integration in the console
            <ExternalLinkIcon size={10} className="ml-1 inline-block align-baseline" />
          </Link>
        )}
        <Link href="/docs/build/production-checklist" className="text-accent hover:underline">
          Production checklist
        </Link>
      </p>
    </DocsSection>
  );
}

/** One boundary column of the pattern facts. */
function PatternOwnedColumn({
  title,
  items,
  accent = false,
}: {
  title: string;
  items: string[];
  accent?: boolean;
}) {
  return (
    <div className="rounded-md border border-line bg-raised/40 p-3">
      <h4 className={`text-sm font-semibold ${accent ? "text-accent" : "text-ink"}`}>{title}</h4>
      <ul className="mt-1.5 space-y-1 text-sm leading-relaxed text-ink-muted">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

/** One linked operation row (method + path verbatim from coverage). */
function OperationRow({ record }: { record: CoverageRecord }) {
  return (
    <li>
      <Link
        href={`/docs/api/${record.operation}`}
        className="inline-flex flex-col gap-0.5 rounded border border-line bg-surface px-2.5 py-1.5 transition-colors hover:border-line-strong"
      >
        <span className="font-mono text-xs text-accent">{record.operation}</span>
        <span className="font-mono text-2xs text-ink-faint">
          {record.method} {record.path}
        </span>
      </Link>
    </li>
  );
}

/**
 * The registry-generated pattern facts every pattern page renders: the
 * three-way boundary, the required operations, the webhook surface, the
 * available evidence, the degradation behavior and the anti-patterns.
 */
function PatternFacts({ pattern }: { pattern: IntegrationPattern }) {
  const operations = pattern.operationIds
    .map((operationId) => coverageByOperation(operationId))
    .filter((record): record is CoverageRecord => Boolean(record));

  return (
    <>
      <DocsSection id="the-boundary" title="The boundary">
        <div className="grid gap-3 md:grid-cols-3">
          <PatternOwnedColumn title="Your application owns" items={pattern.applicationOwns} />
          <PatternOwnedColumn title="ADCOS owns" items={pattern.adcosOwns} accent />
          <PatternOwnedColumn title="Providers own" items={pattern.providerOwns} />
        </div>
      </DocsSection>

      <DocsSection id="required-operations" title="Required operations">
        <p className="text-sm leading-relaxed text-ink-muted">
          The operations this pattern actually needs, from the accepted coverage registry — each
          links to its operation documentation.
        </p>
        <ul className="mt-2 flex flex-col gap-1.5">
          {operations.map((record) => (
            <OperationRow key={record.operation} record={record} />
          ))}
        </ul>
      </DocsSection>

      <DocsSection id="useful-webhooks" title="Useful webhooks">
        <p className="text-sm leading-relaxed text-ink-muted">{pattern.webhookNote}</p>
        <div className="mt-2">
          <OpList operationIds={WEBHOOK_OPERATION_IDS} />
        </div>
        <p className="mt-2 text-xs leading-relaxed text-ink-muted">
          Webhook events are observations, not canonical business state — contract reads remain the
          authority.
        </p>
      </DocsSection>

      <DocsSection id="available-evidence" title="Available evidence">
        <p className="text-sm leading-relaxed text-ink-muted">{EVIDENCE_NOTE}</p>
      </DocsSection>

      <DocsSection id="degradation" title="Degradation and failover">
        <p className="text-sm leading-relaxed text-ink-muted">{pattern.failureNote}</p>
      </DocsSection>

      <DocsSection id="what-not-to-build" title="What NOT to build">
        <ul className="flex flex-col gap-2 text-sm leading-relaxed text-ink-muted">
          {pattern.antiPatterns.map((item) => (
            <li key={item} className="rounded border border-line bg-raised/40 px-3 py-2">
              {item}
            </li>
          ))}
        </ul>
      </DocsSection>
    </>
  );
}

/** The honest not-found state for an unknown build page slug. */
function BuildUnknownState({ pageId }: { pageId: string }) {
  return (
    <DocsPageFrame pageLabel="Build page not found" title="Build page not found">
      <div data-testid={BUILD_PAGE_TEST_IDS.unknown}>
        <div className="rounded-md border border-line bg-surface">
          <EmptyState
            title="No Build page matches this slug"
            description={
              <>
                The Build with ADCOS section has no page with id{" "}
                <span className="font-mono text-ink">{pageId}</span>. The section&apos;s page
                vocabulary is fixed — an unknown id never renders invented guidance.
              </>
            }
            action={
              <Link
                href="/docs/build"
                className="rounded border border-line-strong bg-raised px-3 py-1.5 text-sm text-ink transition-colors hover:bg-surface"
              >
                Back to Build with ADCOS
              </Link>
            }
          />
        </div>
      </div>
    </DocsPageFrame>
  );
}

/* ------------------------------------------------------------------ *
 * /docs/build — the section hub: Choose an integration pattern
 * ------------------------------------------------------------------ */

/** The pattern page slugs (pattern E has no dedicated page — by design). */
const PATTERN_PAGE_HREFS: Partial<Record<string, string>> = {
  application: "/docs/build/application",
  "gateway-relay": "/docs/build/gateway-relay",
  "fleet-subscriber": "/docs/build/fleet-subscriber",
  "provider-adapter": "/docs/build/provider",
};

export function BuildSectionHub() {
  return (
    <DocsPageFrame
      title="Choose an integration pattern"
      lede="This section answers one architectural question completely: I am building a product that needs connectivity — exactly how should ADCOS fit into my architecture? Start with the pattern that matches your product."
    >
      <DocsSection id="the-five-patterns" title="The five integration patterns">
        <p className="text-sm leading-relaxed text-ink-muted">
          Each pattern states what your application owns, what ADCOS owns, what providers own,
          which operations are required, which webhooks are useful, what evidence is available,
          what happens during degradation, and what must not be implemented in the application.
        </p>
        <ul className="mt-2 flex flex-col divide-y divide-line rounded-md border border-line bg-surface">
          {INTEGRATION_PATTERNS.map((pattern) => {
            const patternPageHref = PATTERN_PAGE_HREFS[pattern.id];
            const href = patternPageHref ?? `/build?pattern=${pattern.id}`;
            return (
              <li key={pattern.id} data-testid={BUILD_PAGE_TEST_IDS.patternRow} data-pattern={pattern.id}>
                <Link
                  href={href}
                  className="flex flex-col gap-1 px-4 py-3 transition-colors hover:bg-raised/40"
                >
                  <span className="flex items-center gap-2 text-sm font-medium text-accent">
                    {pattern.title}
                    {!patternPageHref ? (
                      <ExternalLinkIcon size={10} className="text-ink-faint" />
                    ) : null}
                  </span>
                  <span className="text-sm leading-relaxed text-ink-muted">{pattern.summary}</span>
                </Link>
              </li>
            );
          })}
        </ul>
        <p className="mt-2 text-xs leading-relaxed text-ink-muted">
          Four patterns have dedicated pages; the marketplace / orchestration pattern is designed
          directly in the console, where the registry composes its blueprint.
        </p>
      </DocsSection>

      <DocsSection id="design-in-the-console" title="Design in the console">
        <p className="text-sm leading-relaxed text-ink-muted">
          The console&apos;s{" "}
          <Link href="/build" className="text-accent hover:underline">
            Build with ADCOS
            <ExternalLinkIcon size={10} className="ml-1 inline-block align-baseline" />
          </Link>{" "}
          surface turns any pattern into an on-screen integration blueprint: the ordered
          operations, recommended webhooks, the ownership split, boundary rules, failure modes and
          next steps. The blueprint is presentation state for planning — it is not deployment
          configuration and is not persisted.
        </p>
      </DocsSection>

      <DocsSection id="the-rest-of-this-section" title="The rest of this section">
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <Link href="/docs/build/lifecycle" className="text-accent hover:underline">
            Lifecycle implementation
          </Link>
          <Link href="/docs/build/production-checklist" className="text-accent hover:underline">
            Production checklist
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
 * /docs/build/application — Pattern A: application integration
 * ------------------------------------------------------------------ */

export function BuildApplicationPage() {
  const pattern = integrationPatternById("application");
  if (!pattern) return <PatternMissing patternId="application" />;
  return (
    <DocsPageFrame
      pageLabel="Application integration"
      title="Application integration"
      lede="For an application that requires connectivity for itself, a service, or an endpoint cohort: your application asks ADCOS for a technology-neutral connectivity outcome and operates from the resulting contract and observations."
      aside={<span className="font-mono text-xs text-ink-faint">pattern · application</span>}
    >
      <DocsSection id="what-crosses" title="What crosses the boundary">
        <p className="text-sm leading-relaxed text-ink-muted">
          Your application records a technology-neutral connectivity intent; ADCOS reasons about
          eligibility, accepts provider offers onto the intent, and orchestrates fulfillment from
          the activated contract. What crosses the boundary is canonical material — the intent,
          the opaque typed offer references, the activation, and the observations you read back —
          never provider-native objects. The {conceptLinkLabel("connectivity-contract")} is the
          sole durable contract authority.
        </p>
      </DocsSection>
      <PatternFacts pattern={pattern} />
      <BuildWhereNext patternId="application" />
    </DocsPageFrame>
  );
}

/** A concept link rendered inline in curated prose. */
function conceptLinkLabel(conceptId: string): ReactNode {
  return <DocsLink link={conceptLink(conceptId)} />;
}

/** The honest state when the registry does not know a pattern id. */
function PatternMissing({ patternId }: { patternId: string }) {
  return (
    <DocsPageFrame pageLabel="Pattern unavailable" title="Pattern unavailable">
      <div data-testid={BUILD_PAGE_TEST_IDS.unknown}>
        <EmptyState
          title="The integration registry has no such pattern"
          description={
            <>
              No integration pattern with id{" "}
              <span className="font-mono text-ink">{patternId}</span> exists in the registry — this
              page never invents pattern facts.
            </>
          }
          action={
            <Link
              href="/docs/build"
              className="rounded border border-line-strong bg-raised px-3 py-1.5 text-sm text-ink transition-colors hover:bg-surface"
            >
              Back to Build with ADCOS
            </Link>
          }
        />
      </div>
    </DocsPageFrame>
  );
}

/* ------------------------------------------------------------------ *
 * /docs/build/gateway-relay — Pattern B: THE ShareNet reference page
 * ------------------------------------------------------------------ */

/** One step of the canonical boundary diagram (structured markup). */
function BoundaryDiagramStep({
  title,
  note,
  accent = false,
}: {
  title: string;
  note?: string;
  accent?: boolean;
}) {
  return (
    <div
      className={`rounded-md border px-4 py-2.5 text-center ${
        accent ? "border-accent/60 bg-raised" : "border-line bg-surface"
      }`}
    >
      <p className={`text-sm font-semibold ${accent ? "text-ink" : "text-ink"}`}>{title}</p>
      {note ? <p className="mt-0.5 text-xs text-ink-muted">{note}</p> : null}
    </div>
  );
}

export function BuildGatewayRelayPage() {
  const pattern = integrationPatternById("gateway-relay");
  if (!pattern) return <PatternMissing patternId="gateway-relay" />;
  return (
    <DocsPageFrame
      pageLabel="Gateway / relay integration"
      title="Gateway / relay integration"
      lede="For a system such as ShareNet that needs backhaul or gateway/relay connectivity while keeping its own device-to-device distribution plane authoritative — the canonical ShareNet reference integration."
      aside={<span className="font-mono text-xs text-ink-faint">pattern · gateway-relay</span>}
    >
      <DocsSection
        id="canonical-boundary"
        title="The canonical ShareNet boundary"
        description="The reference integration for this pattern (design §13) — ShareNet is an accepted ADCOS vertical proof."
      >
        <div className="flex flex-col items-stretch gap-1.5">
          <BoundaryDiagramStep
            title="ShareNet content/P2P plane"
            note="content, P2P distribution, publisher trust, delivery receipts, application economics"
          />
          <p className="text-center text-xs text-ink-faint">
            ↓ technology-neutral gateway/relay connectivity need
          </p>
          <BoundaryDiagramStep
            title="ADCOS Connectivity Contract"
            note="connectivity contracts and fulfillment"
            accent
          />
          <p className="text-center text-xs text-ink-faint">↓ provider execution</p>
          <BoundaryDiagramStep
            title="Provider realization"
            note="provider-native topology, routing and subscriber authority"
          />
        </div>
        <ul className="mt-3 flex flex-col gap-2 text-sm leading-relaxed text-ink-muted">
          <li>{SHARENET_APPLICATION_AUTHORITY}</li>
          <li>{SHARENET_ADCOS_AUTHORITY}</li>
          <li>{SHARENET_PROVIDER_AUTHORITY}</li>
          <li>{SHARENET_P2P_TRANSFER_RULE}</li>
          <li>{SHARENET_OFFLINE_RULE}</li>
        </ul>
      </DocsSection>

      <DocsSection id="boundary-rules" title="The boundary rules in practice">
        <ul className="flex flex-col gap-2 text-sm leading-relaxed text-ink-muted">
          <li>
            <strong className="font-medium text-ink">Local plane first.</strong> The ShareNet data
            plane — content storage, P2P distribution, delivery receipts — belongs to ShareNet and
            keeps operating when ADCOS is unreachable; ADCOS is the connectivity control plane for
            gateway/relay backhaul, not a dependency of local content availability.
          </li>
          <li>
            <strong className="font-medium text-ink">Technology-neutral asks.</strong> What ShareNet
            records with ADCOS is a technology-neutral gateway/relay connectivity requirement; the
            provider that realizes it, and how, stays behind the provider&apos;s adapter.
          </li>
          <li>
            <strong className="font-medium text-ink">Observations, not authority.</strong>{" "}
            Webhook observations and lifecycle reads inform the gateway controller; the{" "}
            {conceptLinkLabel("connectivity-contract")} read stays canonical.
          </li>
          <li>
            <strong className="font-medium text-ink">Honest evidence.</strong> An accepted contract
            proves a software-side state transition, not physical connectivity — the two evidence
            classes stay distinct.
          </li>
        </ul>
      </DocsSection>

      <DocsSection id="anti-patterns" title="The explicit anti-patterns">
        <ul className="flex flex-col gap-2 text-sm leading-relaxed text-ink-muted">
          <li>
            <strong className="font-medium text-ink">Second contract authority.</strong> Building a
            second connectivity-contract authority beside ADCOS&apos;s — the connectivity contract
            must remain the sole durable authority.
          </li>
          <li>
            <strong className="font-medium text-ink">Provider coupling.</strong> Encoding
            provider-specific topology, or importing provider SDKs, into the ShareNet domain — the
            application speaks only the canonical HTTP developer boundary.
          </li>
          <li>
            <strong className="font-medium text-ink">Webhook-as-authority.</strong> Treating webhook
            observations as canonical business state instead of advisory signals to reconcile
            against contract reads.
          </li>
          <li>
            <strong className="font-medium text-ink">API-success-as-physical-success.</strong>{" "}
            Representing an ADCOS API success as proof that gateway or backhaul connectivity
            physically works.
          </li>
          <li>
            <strong className="font-medium text-ink">Routing local P2P transfers through ADCOS.</strong>{" "}
            Turning ordinary device-to-device content transfers into ADCOS connectivity
            transactions merely because gateway/backhaul connectivity uses ADCOS.
          </li>
        </ul>
      </DocsSection>

      <PatternFacts pattern={pattern} />
      <BuildWhereNext patternId="gateway-relay" />
    </DocsPageFrame>
  );
}

/* ------------------------------------------------------------------ *
 * /docs/build/fleet-subscriber — Pattern C
 * ------------------------------------------------------------------ */

export function BuildFleetSubscriberPage() {
  const pattern = integrationPatternById("fleet-subscriber");
  if (!pattern) return <PatternMissing patternId="fleet-subscriber" />;
  return (
    <DocsPageFrame
      pageLabel="Fleet / subscriber integration"
      title="Fleet / subscriber integration"
      lede="For an application that purchases or allocates connectivity for a defined device or subscriber cohort — without taking provider-native subscriber authority into your product domain."
      aside={<span className="font-mono text-xs text-ink-faint">pattern · fleet-subscriber</span>}
    >
      <DocsSection id="cohort-authority" title="Cohort authority stays application-side">
        <p className="text-sm leading-relaxed text-ink-muted">
          Cohort membership, product policy and the device/user context are yours. ADCOS turns a
          cohort-shaped connectivity requirement into contracts and bounded leases; the provider
          keeps provider-native identity, routing and subscriber authority. Your product never
          becomes a provider subscriber database, and no provider subscriber object enters your
          domain.
        </p>
      </DocsSection>

      <DocsSection id="lease-lifecycle" title="The lease lifecycle">
        <p className="text-sm leading-relaxed text-ink-muted">
          Leases are bounded access windows granted over an active contract — grant, observe,
          renew, revoke:
        </p>
        <ul className="mt-2 flex flex-col gap-1.5">
          {["lease_grant", "leases_list", "lease_get", "lease_renew", "lease_revoke"].map(
            (operationId) => {
              const record = coverageByOperation(operationId);
              return record ? <OperationRow key={operationId} record={record} /> : null;
            },
          )}
        </ul>
        <p className="mt-2 text-xs leading-relaxed text-ink-muted">
          Handle capability-denied, invalid-transition and contract-terminal failures explicitly
          before retrying mutations — canonical reason codes drive the retry decision.
        </p>
      </DocsSection>

      <PatternFacts pattern={pattern} />
      <BuildWhereNext patternId="fleet-subscriber" />
    </DocsPageFrame>
  );
}

/* ------------------------------------------------------------------ *
 * /docs/build/provider — Pattern D
 * ------------------------------------------------------------------ */

export function BuildProviderPage() {
  const pattern = integrationPatternById("provider-adapter");
  if (!pattern) return <PatternMissing patternId="provider-adapter" />;
  return (
    <DocsPageFrame
      pageLabel="Provider integration"
      title="Provider integration"
      lede="For a provider or network operator exposing capabilities into ADCOS without exporting provider-native topology into the application layer."
      aside={<span className="font-mono text-xs text-ink-faint">pattern · provider-adapter</span>}
    >
      <DocsSection id="the-adapter-boundary" title="The adapter boundary">
        <p className="text-sm leading-relaxed text-ink-muted">
          Providers expose connectivity capabilities through ADCOS&apos;s{" "}
          {conceptLinkLabel("provider-adapter-boundary")}. The adapter translates a
          technology-neutral connectivity outcome into the provider&apos;s own realization — and
          that is where provider-native APIs, objects and topology stay. What the application-facing
          surface ever sees are {conceptLinkLabel("provider-capability")} records, offers and
          typed ADCOS outcomes.
        </p>
      </DocsSection>

      <DocsSection id="provider-owned-topology" title="Provider-owned topology">
        <p className="text-sm leading-relaxed text-ink-muted">
          Provider-native topology, routing and subscriber authority remain with the provider.
          There is no universal ADCOS topology graph, and none should be built application-side:
          the application composes over capabilities and contracts, not over provider networks.
          Realization failures surface as typed ADCOS outcomes with canonical reason codes — never
          as raw provider SDK types leaking into the application-facing API.
        </p>
      </DocsSection>

      <DocsSection id="never-leak" title="Never leak provider SDK types">
        <p className="text-sm leading-relaxed text-ink-muted">
          The integration contract is one-directional: provider SDKs and provider-native network
          objects must never appear in application-facing examples, request shapes or domain
          models. Applications integrate with the canonical HTTP developer boundary only; the
          adapter owns every provider-specific detail behind it.
        </p>
      </DocsSection>

      <PatternFacts pattern={pattern} />
      <BuildWhereNext patternId="provider-adapter" />
    </DocsPageFrame>
  );
}

/* ------------------------------------------------------------------ *
 * /docs/build/lifecycle — Lifecycle implementation
 * ------------------------------------------------------------------ */

interface LifecycleStageRow {
  stage: string;
  detail: string;
  operationIds: string[];
}

const LIFECYCLE_STAGES: LifecycleStageRow[] = [
  {
    stage: "Intent",
    detail:
      "The application records a technology-neutral connectivity intent — requirements, hard constraints (immutable once recorded), validity and termination rules.",
    operationIds: ["intent_create", "intents_list", "intent_get"],
  },
  {
    stage: "Eligibility",
    detail:
      "ADCOS reasons about eligibility and policy for the recorded requirement; the lifecycle observation reports the contract state and the backend's own statements.",
    operationIds: ["intent_lifecycle"],
  },
  {
    stage: "Offer",
    detail:
      "Provider offers enter as opaque typed references and are accepted onto the intent (OFFER_SELECTED) — the bridge from requirement to plan.",
    operationIds: ["offers_accept"],
  },
  {
    stage: "Contract",
    detail:
      "Activation moves the contract to CONTRACT_ACTIVE; the canonical contract resource and its referenced usage terms are read from here on.",
    operationIds: ["contract_activate", "contract_get", "contracts_list", "contract_usage"],
  },
  {
    stage: "Execution",
    detail:
      "ADCOS composes the accepted material into an execution plan and executes it; the application observes execution status through the lifecycle read — the plan itself is ADCOS's.",
    operationIds: ["intent_lifecycle"],
  },
  {
    stage: "Provider realization",
    detail:
      "The provider realizes connectivity behind its adapter. There is no provider operation on the accepted boundary, and no provider-native object crosses into the application — realization failures arrive as typed ADCOS outcomes.",
    operationIds: [],
  },
  {
    stage: "Evidence + Assurance",
    detail:
      "Execution records carry an evidence class (software-side evidence is labeled as such — never re-badged as physical proof), and the contract's assurance obligations are read as referenced material.",
    operationIds: ["contract_assurance", "demo_contract_fulfillment", "platform_contract_read"],
  },
];

export function BuildLifecyclePage() {
  return (
    <DocsPageFrame
      pageLabel="Lifecycle implementation"
      title="Lifecycle implementation"
      lede="The canonical sequence mapped to the real operations of the accepted boundary: Intent → Eligibility → Offer → Contract → Execution → provider realization → Evidence + Assurance."
    >
      <ol className="flex flex-col gap-3">
        {LIFECYCLE_STAGES.map((stage, index) => (
          <li key={stage.stage}>
            <DocsSection title={`${index + 1}. ${stage.stage}`}>
              <p className="text-sm leading-relaxed text-ink-muted">{stage.detail}</p>
              {stage.operationIds.length > 0 ? (
                <div className="mt-1">
                  <OpList operationIds={stage.operationIds} />
                </div>
              ) : null}
            </DocsSection>
          </li>
        ))}
      </ol>

      <DocsSection id="idempotency" title="Idempotency">
        <p className="text-sm leading-relaxed text-ink-muted">
          Every mutation request carries an idempotency key. Retries reuse the same key rather than
          creating duplicate records — the boundary answers with the original outcome, and the
          response envelope reports whether the key was replayed.
        </p>
      </DocsSection>

      <DocsSection id="versioning" title="Versioning">
        <p className="text-sm leading-relaxed text-ink-muted">
          The developer API version rides the request path prefix (
          <span className="font-mono text-xs text-ink">/api/2.0</span>). Preserve it verbatim and
          honor the API&apos;s compatibility rules instead of pinning response shapes — canonical
          reason codes and opaque typed references are the stable contract, not the envelope&apos;s
          incidental fields.
        </p>
      </DocsSection>

      <BuildWhereNext />
    </DocsPageFrame>
  );
}

/* ------------------------------------------------------------------ *
 * /docs/build/production-checklist — the §6.8 checklist in full
 * ------------------------------------------------------------------ */

const CHECKLIST_ITEMS: { title: string; detail: string }[] = [
  {
    title: "Authentication",
    detail:
      "Every call authenticates as your application with credentials issued through the developers workspace (the session menu, or the application credential flow). Capability grants unlock operations — check you hold the grant a mutation needs (intents:write, leases:write, webhooks:write) before building. Provider credentials never appear in the application.",
  },
  {
    title: "Versioning",
    detail:
      "The API version rides the request path prefix (/api/2.0). Send it verbatim, read the version from the response envelope, and treat canonical reason codes and opaque typed references — not incidental response fields — as the compatibility contract.",
  },
  {
    title: "Idempotency",
    detail:
      "Every mutation request carries an idempotency key; retries reuse the same key instead of creating duplicate records. Read the envelope's idempotency report to know whether an outcome was replayed.",
  },
  {
    title: "Error handling",
    detail:
      "Canonical reason codes drive retry and repair decisions — never the HTTP status alone. Preserve reason codes verbatim through your own layers; handle capability-denied, invalid-transition and contract-terminal failures explicitly before retrying mutations.",
  },
  {
    title: "Evidence",
    detail:
      "Software evidence and physical/network evidence stay distinct. An API success is never represented as proof of physical connectivity: software-side transitions and records are labeled as software-side, and in this deployment physical/network evidence is NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT — none is fabricated.",
  },
  {
    title: "Degradation",
    detail:
      "Contract reads stay canonical, webhook observations are advisory, and the local data plane keeps operating when ADCOS is unreachable. Making application data-plane availability depend on ADCOS control-plane availability is a product tradeoff — the ShareNet-class rule is that local/P2P planes operate independently — and it must be chosen explicitly, never inherited by accident.",
  },
];

export function BuildChecklistPage() {
  return (
    <DocsPageFrame
      pageLabel="Production checklist"
      title="Production checklist"
      lede="The honest operating contract before you ship an ADCOS integration: authentication, versioning, idempotency, error handling, evidence and degradation behavior."
    >
      <ul className="flex flex-col gap-3">
        {CHECKLIST_ITEMS.map((item) => (
          <li key={item.title}>
            <DocsSection title={item.title}>
              <p className="flex items-start gap-2 text-sm leading-relaxed text-ink-muted">
                <span aria-hidden="true" className="mt-0.5 text-accent">
                  ✓
                </span>
                <span>{item.detail}</span>
              </p>
            </DocsSection>
          </li>
        ))}
      </ul>
      <DocsSection id="surfaces-behind-the-checklist" title="The surfaces behind the checklist">
        <p className="text-sm leading-relaxed text-ink-muted">
          The real operations the checklist keeps referring to — identity and capability grants,
          the idempotent mutation core, the canonical contract read, and the webhook observation
          surface:
        </p>
        <div className="mt-1">
          <OpList operationIds={["application_self", "intent_create", "contract_get", "endpoint_register"]} />
        </div>
      </DocsSection>
      <BuildWhereNext />
    </DocsPageFrame>
  );
}

/* ------------------------------------------------------------------ *
 * The page registry (the [id] route + the docs home IA entries)
 * ------------------------------------------------------------------ */

interface BuildPageMeta {
  id: string;
  title: string;
  description: string;
  component: ComponentType;
}

export const BUILD_PAGES: BuildPageMeta[] = [
  {
    id: "application",
    title: "Application integration",
    description:
      "Pattern A — your application asks ADCOS for a technology-neutral connectivity outcome and operates from the contract and observations.",
    component: BuildApplicationPage,
  },
  {
    id: "gateway-relay",
    title: "Gateway / relay integration",
    description:
      "Pattern B — the canonical ShareNet reference: backhaul connectivity through ADCOS while the content/P2P plane stays authoritative.",
    component: BuildGatewayRelayPage,
  },
  {
    id: "fleet-subscriber",
    title: "Fleet / subscriber integration",
    description:
      "Pattern C — allocate connectivity for a device or subscriber cohort; the lease lifecycle; cohort authority stays application-side.",
    component: BuildFleetSubscriberPage,
  },
  {
    id: "provider",
    title: "Provider integration",
    description:
      "Pattern D — expose capabilities through the ADCOS adapter boundary; provider-owned topology never leaks into the application layer.",
    component: BuildProviderPage,
  },
  {
    id: "lifecycle",
    title: "Lifecycle implementation",
    description:
      "The canonical sequence — Intent → Eligibility → Offer → Contract → Execution → realization → Evidence + Assurance — mapped to the real operations.",
    component: BuildLifecyclePage,
  },
  {
    id: "production-checklist",
    title: "Production checklist",
    description:
      "Authentication, versioning, idempotency, error handling, evidence and degradation behavior — the honest operating contract.",
    component: BuildChecklistPage,
  },
];

/** Look up one build page by its slug. */
export function buildPageById(pageId: string): BuildPageMeta | undefined {
  return BUILD_PAGES.find((page) => page.id === pageId);
}

/**
 * The dispatcher the /docs/build/[id] route renders: the curated page
 * for a known slug, the honest not-found state for an unknown one.
 */
export function BuildPatternDocPage({ pageId }: { pageId: string }) {
  const page = buildPageById(pageId);
  if (!page) return <BuildUnknownState pageId={pageId} />;
  const Page = page.component;
  return <Page />;
}

/** The docs home IA entries for the Build section (design §8). */
export function buildDocsHomeEntries(): {
  title: string;
  href: string;
  description: string;
  leaves?: boolean;
}[] {
  return [
    ...BUILD_PAGES.map((page) => ({
      title: page.title,
      href: `/docs/build/${page.id}`,
      description: page.description,
    })),
    {
      title: "Design this integration in the console",
      href: "/build",
      description:
        "The /build surface composes an on-screen integration blueprint from the same registry — presentation state for planning, never deployment configuration.",
      leaves: true,
    },
  ];
}
