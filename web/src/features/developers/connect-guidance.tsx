"use client";

/**
 * ConnectGuidance — the honest disconnected state for the Developers
 * area (work order deliverable #5): link the shell's session flow and
 * NEVER fake application data.
 *
 * The connect flow lives in the shell (the session menu in the top
 * bar opens the connect dialog, which validates the application id +
 * credential against GET /api/2.0/application and holds the session
 * in memory only). This card points there and reproduces the exact
 * request the flow makes — no invented credential material, ever.
 */

import { ApiRequestPanel } from "@/components/ui";

export function ConnectGuidance({ lead }: { lead: string }) {
  return (
    <section
      data-testid="connect-guidance"
      className="rounded-md border border-line bg-surface p-4"
    >
      <h2 className="text-sm font-semibold text-ink">No application connected</h2>
      <p className="mt-1 text-sm text-ink-muted">{lead}</p>
      <p className="mt-2 text-sm text-ink-muted">
        Open the session menu (top right) and choose{" "}
        <span className="font-medium text-ink">Connect application</span>. The
        dialog validates the credential against the boundary before a session
        is accepted; the credential is held in memory only and a reload clears
        it by design.
      </p>
      <p className="mt-2 text-sm text-ink-muted">
        In the local sandbox, the runtime prints the demo application id and
        credential at startup — use those.
      </p>
      <p className="mt-3 text-xs text-ink-faint">
        The request the connect flow validates against:
      </p>
      <div className="mt-1">
        <ApiRequestPanel variant="compact" method="GET" path="/api/2.0/application" />
      </div>
    </section>
  );
}
