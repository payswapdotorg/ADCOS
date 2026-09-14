/**
 * The command registry — the palette's source of navigable/actions.
 *
 * A module-level store (same pattern as the request log): any feature can
 * register commands on mount and unregister on unmount; the palette
 * subscribes via `useCommands` (useSyncExternalStore). Re-registering an
 * existing id REPLACES the record (safe under StrictMode double-effects).
 */

import { useSyncExternalStore, type ReactNode } from "react";

/** One palette-actionable command. */
export interface CommandRecord {
  /** Stable id (namespaced by the owner, e.g. "nav-home"). */
  id: string;
  /** The title shown (and fuzzy-matched) in the palette. */
  title: string;
  /** Extra match material (lower relevance than the title by construction). */
  keywords?: string[];
  /** Optional leading icon (a rendered element, sized by the owner). */
  icon?: ReactNode;
  /** Navigation target — executed via the router by the palette mount. */
  href?: string;
  /** Imperative action (used when there is no href). */
  run?: () => void;
  /** Grouping label ("Navigate", "Actions", ...). */
  group?: string;
}

let commands: CommandRecord[] = [];
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/**
 * Register a command (replaces any record with the same id).
 * Returns the unregister function for effect cleanup.
 */
export function registerCommand(record: CommandRecord): () => void {
  const existing = commands.findIndex((command) => command.id === record.id);
  commands =
    existing >= 0
      ? commands.map((command, index) => (index === existing ? record : command))
      : [...commands, record];
  emit();
  return () => unregisterCommand(record.id);
}

/** Remove the command with this id (no-op when absent). */
export function unregisterCommand(id: string): void {
  if (!commands.some((command) => command.id === id)) return;
  commands = commands.filter((command) => command.id !== id);
  emit();
}

/** The currently registered commands (registration order). */
export function getCommands(): CommandRecord[] {
  return commands;
}

/** Subscribe to registry changes (useSyncExternalStore contract). */
export function subscribeCommands(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** React binding for the registry. */
export function useCommands(): CommandRecord[] {
  return useSyncExternalStore(subscribeCommands, getCommands, getCommands);
}

/** Test helper — reset the registry between suites. */
export function __resetCommandRegistryForTests(): void {
  commands = [];
  emit();
}
