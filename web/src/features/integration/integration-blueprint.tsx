/**
 * IntegrationBlueprintView — renders ONE integration blueprint produced
 * by the registry's `buildIntegrationBlueprint(patternId,
 * selectedCapabilityIds)` (the frozen Build-with-ADCOS design §7).
 *
 * The blueprint is PRESENTATION STATE, not a new domain authority: this
 * component renders it on screen with the honest disclosure pinned to
 * the top, and every identifier resolves into the canonical registries —
 * operations through `@/lib/api/coverage` (linked to their operation
 * documentation), capabilities through `@/lib/integration`. Nothing here
 * persists state, provisions resources or claims deployment
 * configuration.
 *
 * Pure render (no hooks, no browser APIs) — works from both server and
 * client components; the interactive parent (build-with-adcos.tsx) owns
 * the selection state.
 */

import Link from "next/link";
import type { ReactNode } from "react";
import { coverageByOperation } from "@/lib/api/coverage";
import {
  INTEGRATION_CAPABILITIES,
  integrationPatternById,
  type IntegrationBlueprint,
} from "@/lib/integration";

/** Stable test ids for the blueprint rendering. */
export const BLUEPRINT_TEST_IDS = {
  root: "integration-blueprint",
  disclosure: "integration-blueprint-disclosure",
  operation: "integration-blueprint-operation",
  ownedColumn: "integration-blueprint-owned",
} as const;

/** The honest disclosure (design §7 — presentation state, not authority). */
export const BLUEPRINT_DISCLOSURE =
  "This blueprint is on-screen presentation state for planning. It is not deployment configuration, it is not persisted, and it provisions nothing — the connectivity contract and the accepted API coverage remain the only authorities.";

/**
 * The path prefixes a blueprint next-step string may carry. Console/docs
 * routes render as Links; the public LLM assets render as plain anchors
 * (they are static files, not app routes).
 */
const NEXT_STEP_PATH_PATTERN =
  /(\/(?:docs|developers\/explorer|build|quickstart|playbooks|tour|llms\.txt|llms-full\.txt|adcos-integration-context\.json|adcos-capabilities\.json|adcos-operations\.json)[A-Za-z0-9\-._/?=&#]*)/g;

const LLM_ASSET_PREFIXES = ["/llms", "/adcos-"];

function isLlmAssetPath(path: string): boolean {
  return LLM_ASSET_PREFIXES.some((prefix) => path.startsWith(prefix));
}

/** Render one next-step string, linkifying the paths it mentions. */
export function NextStepLine({ text }: { text: string }) {
  const parts = text.split(NEXT_STEP_PATH_PATTERN);
  const rendered: ReactNode[] = parts.map((part, index) => {
    if (index % 2 === 1) {
      return isLlmAssetPath(part) ? (
        <a
          key={`${index}-${part}`}
          href={part}
          className="rounded font-mono text-xs text-accent hover:underline"
        >
          {part}
        </a>
      ) : (
        <Link
          key={`${index}-${part}`}
          href={part}
          className="rounded font-mono text-xs text-accent hover:underline"
        >
          {part}
        </Link>
      );
    }
    return <span key={`text-${index}`}>{part}</span>;
  });
  return <li className="leading-6">{rendered}</li>;
}

/** One owned-object column of the three-way boundary. */
function OwnedColumn({
  title,
  items,
  accent = false,
}: {
  title: string;
  items: string[];
  accent?: boolean;
}) {
  return (
    <div
      data-testid={BLUEPRINT_TEST_IDS.ownedColumn}
      data-owner={title}
      className="rounded-xl border border-line bg-base/30 p-4"
    >
      <h4 className={`text-sm font-semibold ${accent ? "text-accent" : "text-ink"}`}>{title}</h4>
      <ul className="mt-2 space-y-1.5 text-sm leading-6 text-ink-muted">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export function IntegrationBlueprintView({ blueprint }: { blueprint: IntegrationBlueprint }) {
  const pattern = integrationPatternById(blueprint.patternId);
  const capabilities = blueprint.selectedCapabilityIds
    .map((id) => INTEGRATION_CAPABILITIES.find((capability) => capability.id === id))
    .filter((capability): capability is NonNullable<typeof capability> => Boolean(capability));

  return (
    <div
      data-testid={BLUEPRINT_TEST_IDS.root}
      data-pattern={blueprint.patternId}
      className="rounded-2xl border border-accent/50 bg-surface"
    >
      <div className="border-b border-line p-5 lg:p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-faint">
          Integration blueprint
        </p>
        <h3 className="mt-2 text-xl font-semibold text-ink">
          {pattern?.title ?? blueprint.patternId}
        </h3>
        <p className="mt-1 font-mono text-2xs text-ink-faint">pattern · {blueprint.patternId}</p>
        <p
          data-testid={BLUEPRINT_TEST_IDS.disclosure}
          className="mt-3 rounded-lg border border-line bg-base/40 px-3 py-2 text-xs leading-5 text-ink-muted"
        >
          {BLUEPRINT_DISCLOSURE}
        </p>
      </div>

      <div className="flex flex-col gap-6 p-5 lg:p-6">
        {capabilities.length > 0 ? (
          <div>
            <h4 className="text-sm font-semibold text-ink">Selected capabilities</h4>
            <div className="mt-2 flex flex-wrap gap-2">
              {capabilities.map((capability) => (
                <span
                  key={capability.id}
                  className="rounded-full border border-line bg-base/30 px-3 py-1.5 text-xs text-ink-muted"
                >
                  {capability.title}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <h4 className="text-sm font-semibold text-ink">
              Required operations, in integration order
            </h4>
            <ol className="mt-2 space-y-2">
              {blueprint.requiredOperationIds.map((operationId, index) => {
                const record = coverageByOperation(operationId);
                return (
                  <li
                    key={`${operationId}-${index}`}
                    data-testid={BLUEPRINT_TEST_IDS.operation}
                    data-operation={operationId}
                  >
                    {record ? (
                      <Link
                        href={`/docs/api/${record.operation}`}
                        className="flex items-baseline gap-2 rounded-lg border border-line bg-base/30 p-3 hover:bg-raised/60"
                      >
                        <span className="font-mono text-2xs text-ink-faint">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <span>
                          <span className="font-mono text-xs text-accent">
                            {record.method} {record.path}
                          </span>
                          <span className="mt-0.5 block text-sm text-ink">{record.operation}</span>
                        </span>
                      </Link>
                    ) : (
                      <span className="block rounded-lg border border-line bg-base/30 p-3 font-mono text-xs text-ink-muted">
                        {operationId} — not in the accepted coverage registry
                      </span>
                    )}
                  </li>
                );
              })}
            </ol>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-ink">Recommended webhook events</h4>
            {blueprint.recommendedWebhookEventIds.length > 0 ? (
              <>
                <ul className="mt-2 flex flex-wrap gap-2">
                  {blueprint.recommendedWebhookEventIds.map((eventId) => (
                    <li
                      key={eventId}
                      className="rounded-full border border-line bg-base/30 px-3 py-1.5 font-mono text-xs text-ink-muted"
                    >
                      {eventId}
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-xs leading-5 text-ink-muted">
                  Webhook events are observations, not canonical business state — contract reads
                  remain the authority.
                </p>
              </>
            ) : (
              <p className="mt-2 text-sm leading-6 text-ink-muted">
                No webhook events recommended for this selection.
              </p>
            )}
            {pattern ? (
              <p className="mt-3 text-xs leading-5 text-ink-muted">{pattern.webhookNote}</p>
            ) : null}
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <OwnedColumn title="Your application owns" items={blueprint.applicationOwnedObjects} />
          <OwnedColumn title="ADCOS owns" items={blueprint.adcosOwnedObjects} accent />
          <OwnedColumn title="Provider owns" items={blueprint.providerOwnedObjects} />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <h4 className="text-sm font-semibold text-ink">Boundary rules</h4>
            <ul className="mt-2 space-y-2 text-sm leading-6 text-ink-muted">
              {blueprint.boundaryRules.map((rule) => (
                <li key={rule} className="rounded-lg border border-line bg-base/30 px-3 py-2">
                  {rule}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-ink">Failure modes to handle</h4>
            <ul className="mt-2 space-y-2 text-sm leading-6 text-ink-muted">
              {blueprint.failureModes.map((mode) => (
                <li key={mode} className="rounded-lg border border-line bg-base/30 px-3 py-2">
                  {mode}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div>
          <h4 className="text-sm font-semibold text-ink">Next steps</h4>
          <ul className="mt-2 space-y-1.5 text-sm text-ink-muted">
            {blueprint.nextSteps.map((step) => (
              <NextStepLine key={step} text={step} />
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
