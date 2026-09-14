"use client";

/**
 * Section — the settings page's bordered section wrapper (one visual
 * language with the console's object surfaces).
 */

import type { ReactNode } from "react";

export function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section
      aria-labelledby={id}
      className="rounded-md border border-line bg-surface"
    >
      <div className="border-b border-line px-4 py-3">
        <h2 id={id} className="text-sm font-semibold text-ink">
          {title}
        </h2>
        <p className="mt-0.5 text-sm text-ink-muted">{description}</p>
      </div>
      <div className="px-4 py-4">{children}</div>
    </section>
  );
}
