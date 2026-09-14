/**
 * The recent-objects store — where the palette (and later list surfaces)
 * record what the operator actually visited, so the palette self-feeds a
 * "Recent" section.
 *
 * Display DATA only (never authority): recents are hints for navigation,
 * not a cache of backend truth. In-memory, capped at 8, newest first,
 * deduplicated by href. NO secrets, NO response payloads — just kind,
 * id, label and href.
 */

import { useSyncExternalStore } from "react";

export interface RecentObject {
  /** The object family ("route", "contract", "lease", ...). */
  kind: string;
  /** The backend-minted id (or the href for plain routes). */
  id: string;
  /** What the palette row shows. */
  label: string;
  /** Where the row navigates. */
  href: string;
  /** ISO timestamp of the visit. */
  at: string;
}

const MAX_RECENTS = 8;

let recents: RecentObject[] = [];
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/**
 * Record a visit: newest-first, deduplicated by href, capped at 8.
 * Re-recording an href refreshes its position and timestamp.
 */
export function addRecent(object: RecentObject): void {
  recents = [object, ...recents.filter((entry) => entry.href !== object.href)].slice(
    0,
    MAX_RECENTS,
  );
  emit();
}

/** The current recents (newest first). */
export function getRecentObjects(): RecentObject[] {
  return recents;
}

/** Clear all recents. */
export function clearRecentObjects(): void {
  recents = [];
  emit();
}

/** Subscribe to recents changes (useSyncExternalStore contract). */
export function subscribeRecentObjects(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** React binding for the recents store. */
export function useRecentObjects(): RecentObject[] {
  return useSyncExternalStore(subscribeRecentObjects, getRecentObjects, getRecentObjects);
}

/** Test helper — reset the store between suites. */
export function __resetRecentObjectsForTests(): void {
  recents = [];
  emit();
}
