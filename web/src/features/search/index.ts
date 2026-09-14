/**
 * Search infrastructure — the command palette's data layer and mount.
 *
 * - `fuzzy`: the pure matcher (subsequence + scoring)
 * - `command-registry`: the registered commands (navigate/actions)
 * - `recent-objects`: the recently-visited objects (display data only)
 * - `command-palette-mount`: the wired-up palette the shell renders
 */

export { fuzzyMatch } from "./fuzzy";
export {
  registerCommand,
  unregisterCommand,
  getCommands,
  subscribeCommands,
  useCommands,
  __resetCommandRegistryForTests,
  type CommandRecord,
} from "./command-registry";
export {
  addRecent,
  getRecentObjects,
  clearRecentObjects,
  subscribeRecentObjects,
  useRecentObjects,
  __resetRecentObjectsForTests,
  type RecentObject,
} from "./recent-objects";
export { CommandPaletteMount } from "./command-palette-mount";
