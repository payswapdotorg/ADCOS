"use client";
import "@/features/eligibility/fetch-binding-shim";

/**
 * NetworksView — provider/adapter inspection built ONLY from what the
 * backend actually exposes:
 *
 * - the execution composition facts from the default demonstration
 *   document (provider, adapter, access technology, standard
 *   mechanisms, the sandbox position, the SOFTWARE evidence class);
 * - the provider-topology BOUNDARY notice — provider-native topology,
 *   routing and subscriber authority remain provider-owned; no
 *   topology graph is ever drawn here;
 * - the consumed backends from GET /readyz (verbatim states/details);
 * - an honest "what this page does not show" section for the
 *   health/performance metrics and eligibility lists this deployment
 *   does not expose — none are invented.
 *
 * Both reads are platform routes and work without a session; refresh
 * re-fetches truth (no cache — React state holds presentation only).
 */

import { useSession } from "@/lib/session";
import type { DemoDocument, Readiness } from "@/lib/api/types";
import { useAdcosRead } from "@/features/eligibility";
import { ObjectSection } from "@/features/eligibility";
import { RefreshIcon } from "@/components/ui";
import { CompositionSection } from "./composition-section";
import { ConsumedBackendsSection } from "./consumed-backends-section";

export function NetworksView() {
  const { client } = useSession();

  // platform reads — both work without a session
  const compositionRead = useAdcosRead<DemoDocument>(
    () => client.demoContractFulfillment(),
    [client],
  );
  const readinessRead = useAdcosRead<Readiness>(() => client.readyz(), [
    client,
  ]);

  const refreshing = compositionRead.loading || readinessRead.loading;

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Networks</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Provider and adapter facts as exposed by this deployment.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            compositionRead.refresh();
            readinessRead.refresh();
          }}
          disabled={refreshing}
          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface disabled:opacity-60"
        >
          <RefreshIcon size={14} />
          {refreshing ? "refreshing…" : "Refresh"}
        </button>
      </header>

      <div className="flex flex-col gap-4">
        <CompositionSection read={compositionRead} />

        <aside
          aria-label="Provider topology boundary"
          className="rounded-md border border-dashed border-warning/60 bg-warning/5 px-4 py-3"
        >
          <p className="text-2xs uppercase tracking-wide text-ink-faint">
            provider-owned boundary
          </p>
          <p className="mt-1 text-sm leading-relaxed text-ink-muted">
            Provider topology remains provider-owned: this deployment does
            not expose a topology graph. ADCOS composes provider-supplied
            capabilities without owning provider-native topology, routing or
            subscriber authority — no topology graph is rendered here.
          </p>
        </aside>

        <ConsumedBackendsSection read={readinessRead} />

        <ObjectSection
          id="networks-not-shown"
          title="What this page does not show"
          description="Honest absences — nothing here is invented."
        >
          <ul className="flex flex-col gap-2.5">
            <li className="flex flex-col gap-0.5">
              <span className="text-sm text-ink">
                Observed health &amp; performance
              </span>
              <span className="text-sm text-ink-muted">
                No provider health or performance metrics are exposed by
                this deployment — none are invented here.
              </span>
            </li>
            <li className="flex flex-col gap-0.5">
              <span className="text-sm text-ink">Eligibility lists</span>
              <span className="text-sm text-ink-muted">
                Provider eligibility decisions are not exposed by this
                deployment; the eligibility presentation for contracts lives
                on each contract&apos;s detail page.
              </span>
            </li>
          </ul>
        </ObjectSection>
      </div>
    </div>
  );
}
