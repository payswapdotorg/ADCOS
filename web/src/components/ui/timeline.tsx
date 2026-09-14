/**
 * Timeline — an ordered event rail. Dots take the tone of the backend
 * state value when one is given (statusToneFor), so lifecycle events
 * read with the same colors as Status everywhere else.
 */

import type { ReactNode } from "react";
import { statusToneFor } from "@/lib/design/tokens";
import { cn } from "@/lib/utils";
import { TONE_DOT_CLASSES } from "./status";

export interface TimelineItem {
  id: string;
  /** RFC 3339-ish instant label (rendered mono, faint). */
  time?: string;
  title: string;
  description?: ReactNode;
  /** A backend state value; resolved through the shared tone map. */
  tone?: string;
}

export function Timeline({ items }: { items: TimelineItem[] }) {
  if (items.length === 0) return null;
  return (
    <ol className="flex flex-col">
      {items.map((item, index) => {
        const tone = item.tone ? statusToneFor(item.tone) : "neutral";
        const last = index === items.length - 1;
        return (
          <li key={item.id} className="relative flex gap-3">
            <span className="flex flex-col items-center pt-1" aria-hidden="true">
              <span
                className={cn("h-2 w-2 shrink-0 rounded-full", TONE_DOT_CLASSES[tone])}
              />
              {last ? null : <span className="mt-1 w-px flex-1 bg-line" />}
            </span>
            <div className={cn("min-w-0 flex-1", !last && "pb-4")}>
              {item.time ? (
                <div className="font-mono text-2xs text-ink-faint">
                  {item.time}
                </div>
              ) : null}
              <div className="text-sm text-ink">{item.title}</div>
              {item.description ? (
                <div className="text-sm text-ink-muted">{item.description}</div>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
