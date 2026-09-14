"use client";

/**
 * ConnectGuidance — the honest gate for authenticated developer-API
 * surfaces: when no application session is held, the read/mutation is NOT
 * fired (the fetcher is suspended through useAdcosRead) and the developer
 * is told exactly how to connect. Credentials live in memory only.
 */

import { EmptyState } from "@/components/ui";

export function ConnectGuidance({ lead }: { lead: string }) {
  return (
    <section
      aria-labelledby="connect-guidance-heading"
      className="rounded-md border border-line bg-surface"
      data-testid="connect-guidance"
    >
      <EmptyState
        title="Connect an application to continue"
        description={
          <>
            {lead} Open the session menu at the top right and choose{" "}
            <span className="font-medium text-ink">Connect application</span> — the
            credential is held in memory only, and a reload clears the session by
            design.
          </>
        }
      />
    </section>
  );
}
