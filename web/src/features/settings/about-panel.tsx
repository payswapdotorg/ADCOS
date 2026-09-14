"use client";

/**
 * AboutPanel — the console's own boundary statement (Worker 3, Part C):
 * no second authority; the canonical backend owns all state. Plus the
 * link into the error workbench (the FROZEN path /settings/errors).
 */

import { ErrorWorkbenchLink } from "@/features/errors/link";

/** Stable test id for the settings suite. */
export const ABOUT_PANEL_TEST_ID = "settings-about";

export function AboutPanel() {
  return (
    <div
      className="flex flex-col gap-3"
      data-testid={ABOUT_PANEL_TEST_ID}
    >
      <p className="text-sm leading-relaxed text-ink-muted">
        This console is a presentation and control surface —{" "}
        <span className="font-medium text-ink">
          not a second authority
        </span>
        . The canonical ADCOS backend owns all state: contracts, plans,
        execution, evidence, assurance, provider state, credentials, policy
        and eligibility. React state here holds presentation only; every
        refresh re-fetches truth from the backend.
      </p>
      <p className="text-sm leading-relaxed text-ink-muted">
        Every meaningful UI mutation maps to a backend operation and exposes
        its API representation; software evidence is never presented as
        physical connectivity; provider-native topology, routing and
        subscriber authority remain provider-owned. The console is not a
        second execution engine.
      </p>
      <p className="text-sm leading-relaxed text-ink-muted">
        Troubleshooting: every failed request this session made is captured
        with its full anatomy —{" "}
        <ErrorWorkbenchLink>open the error workbench</ErrorWorkbenchLink>.
      </p>
    </div>
  );
}
