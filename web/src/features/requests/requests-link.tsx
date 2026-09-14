"use client";

/**
 * The request-inspector linkage — the object-page affordance.
 *
 * Other console surfaces deep-link a captured request into the Request
 * Inspector with `requestsHref(sequence)` (or the `RequestsLink`
 * component): the inspector opens with that request preselected in its
 * detail drawer. The error workbench already adopted the same shape
 * (`workbenchHref`), so every surface can route an operator from "what
 * happened" straight to the exact wire record.
 */

import type { ReactNode } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

/** The Request Inspector route. */
export const REQUESTS_INSPECTOR_PATH = "/developers/requests";

/** The href that focuses one captured request in the inspector. */
export function requestsHref(sequence?: number): string {
  return sequence === undefined
    ? REQUESTS_INSPECTOR_PATH
    : `${REQUESTS_INSPECTOR_PATH}?request=${sequence}`;
}

/** A link to the inspector, optionally focused on one captured request. */
export function RequestsLink({
  sequence,
  className,
  children,
}: {
  /** The captured request's sequence (deep-links the detail drawer). */
  sequence?: number;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Link
      href={requestsHref(sequence)}
      className={cn("text-accent hover:underline", className)}
    >
      {children}
    </Link>
  );
}
