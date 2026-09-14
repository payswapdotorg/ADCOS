"use client";

/**
 * GettingStartedCard — the calm three-step guidance for a FRESH account
 * (connected, zero contracts). Text-only: no metrics, no decoration —
 * just the honest path from connect → builder → demonstration.
 */

import Link from "next/link";
import { ObjectSection } from "@/features/eligibility";

export function GettingStartedCard({ className }: { className?: string }) {
  return (
    <ObjectSection
      id="home-getting-started"
      title="Getting started"
      description="A fresh account — three steps to a fulfilled connectivity chain."
      className={className}
    >
      <ol className="grid gap-3 sm:grid-cols-3">
        <li className="flex flex-col gap-1">
          <span className="font-mono text-2xs text-ink-faint">step 1</span>
          <span className="text-sm leading-relaxed text-ink">
            Connect an application — this session is connected. The session
            menu (top right) holds the credential in memory only.
          </span>
        </li>
        <li className="flex flex-col gap-1">
          <span className="font-mono text-2xs text-ink-faint">step 2</span>
          <span className="text-sm leading-relaxed text-ink">
            Record your first connectivity intent —{" "}
            <Link
              href="/connectivity"
              className="text-accent transition-colors hover:text-ink"
            >
              New contract
            </Link>{" "}
            opens the builder; the contract enters INTENT awaiting offer
            selection.
          </span>
        </li>
        <li className="flex flex-col gap-1">
          <span className="font-mono text-2xs text-ink-faint">step 3</span>
          <span className="text-sm leading-relaxed text-ink">
            Run the{" "}
            <a
              href="#home-demo"
              className="text-accent transition-colors hover:text-ink"
            >
              fulfillment demonstration
            </a>{" "}
            below — the deterministic full chain, no authentication.
          </span>
        </li>
      </ol>
    </ObjectSection>
  );
}
