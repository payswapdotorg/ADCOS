/**
 * The Playbooks feature (the DEC-0128 program, Task 6 of the frozen
 * plan — docs/superpowers/plans/2026-09-14-adcos-console-v2-learning-
 * experience.md; the frozen V2 design §11).
 *
 * The goal-oriented guided paths, GENERATED from the Task-1 guide
 * registry (`@/lib/education` GUIDES — the seven playbooks):
 * - `playbook-index` — the /playbooks index, grouped by experience goal
 *   (Build / Understand / Integrate / Diagnose) with the route-local
 *   search;
 * - `playbook-page` — one guide's stepped walkthrough with progress,
 *   the real step-link affordances and the "Open in workbench" handoff;
 * - `playbook-links` — the kind-aware link affordances carrying the
 *   mirrored `?from=` return-path convention;
 * - `playbook-context` — the mirrored contextual return slot.
 *
 * Registry data only: every education string comes from the W1
 * registries; every step link resolves against the frozen vocabularies;
 * unknown ids render honest unknown states. The Quickstart journey
 * (`quickstart*` files, plan Task 5) is the W2 wave's surface and is
 * deliberately NOT part of this barrel.
 */

export { PlaybookIndex, PLAYBOOK_INDEX_TEST_IDS } from "./playbook-index";
export { PlaybookPage, PLAYBOOK_PAGE_TEST_IDS } from "./playbook-page";
export {
  StepLinkAffordance,
  OperationDeepLink,
  withFrom,
  playbookPath,
} from "./playbook-links";
export {
  PlaybookContextSlot,
  PLAYBOOK_RETURN_PATH_TEST_ID,
} from "./playbook-context";

export const PLAYBOOKS_FEATURE = {
  area: "playbooks",
  route: "/playbooks",
  owner: "w3-expert-handoff",
  planTask: "Task 6 — Playbooks (the frozen V2 design §11)",
  hardRule:
    "generated from the guide registry, never a second playbook authority; honest wording rendered verbatim",
} as const;
