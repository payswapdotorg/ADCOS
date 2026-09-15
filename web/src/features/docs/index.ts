/**
 * The docs feature (the Console V2 documentation system — DEC-0128,
 * Task 3 of the frozen plan: docs/superpowers/plans/2026-09-14-adcos-
 * console-v2-learning-experience.md).
 *
 * User-facing documentation, distinct from the internal architecture/
 * evidence records (the frozen V2 design §9/§19). The registry-driven
 * pages (concepts, guides, API, reference, errors) are GENERATED from
 * the Task-1 education registry (`@/lib/education`), the coverage
 * registry (`@/lib/api/coverage`) and the canonical error taxonomy
 * (`@/lib/api/errors`) — never a second authority. The Start here
 * pages, the SDK page, and the Troubleshooting topics are curated, and
 * every curated sentence follows the design's truth rules: where the
 * current deployment differs from the conceptual model, the §17
 * pattern states it. The route-local search filters registry data in
 * the browser only — no backend search service.
 */

export const DOCS_FEATURE = {
  area: "docs",
  route: "/docs",
  owner: "w1c-documentation",
  planTask: "Task 3 — Documentation (the frozen V2 design §9)",
  hardRule:
    "generated from the Task-1 registries, never a second authority; user-facing documentation distinct from internal architecture records",
} as const;

// the docs home (the IA itself, with the route-local search)
export { DocsHome, DOCS_HOME_TEST_IDS } from "./docs-home";

// the curated Start here pages
export {
  StartHereHub,
  WhatIsAdcosPage,
  HowAdcosWorksPage,
  FirstContractPage,
  REPLAN_EVENTS_DISCLOSURE,
} from "./start-pages";

// the Concepts index and page (GENERATED from the concept registry)
export { ConceptIndex, CONCEPT_INDEX_TEST_IDS } from "./concept-index";
export {
  ConceptPage,
  CONCEPT_PAGE_TEST_IDS,
  CONCEPT_SIX_QUESTIONS,
} from "./concept-page";

// the Guides index and page (GENERATED from the guide registry)
export { GuideIndex, GUIDE_INDEX_TEST_IDS } from "./guide-index";
export { GuidePage, GUIDE_PAGE_TEST_IDS } from "./guide-page";

// the Build with ADCOS section (the frozen Build-with-ADCOS design §8:
// the hub, the four pattern pages, the ShareNet reference, the lifecycle
// implementation and the production checklist — pattern facts GENERATED
// from the integration registry)
export {
  BUILD_DOCS_SECTION,
  BUILD_PAGE_TEST_IDS,
  BUILD_PAGES,
  BuildApplicationPage,
  BuildChecklistPage,
  BuildFleetSubscriberPage,
  BuildGatewayRelayPage,
  BuildLifecyclePage,
  BuildPatternDocPage,
  BuildProviderPage,
  BuildSectionHub,
  SHARENET_ADCOS_AUTHORITY,
  SHARENET_APPLICATION_AUTHORITY,
  SHARENET_OFFLINE_RULE,
  SHARENET_P2P_TRANSFER_RULE,
  SHARENET_PROVIDER_AUTHORITY,
  buildDocsHomeEntries,
  buildPageById,
} from "./build-pages";

// the API hub and operation page (GENERATED from coverage + education)
export { ApiHub, API_HUB_TEST_IDS } from "./api-hub";
export { OperationPage, OPERATION_PAGE_TEST_IDS } from "./operation-page";

// the honest SDK page
export { SdkPage, SDK_PAGE_TEST_IDS, SDK_DISCLOSURE } from "./sdk-page";

// the canonical reason codes (verbatim) with human guidance
export {
  ErrorsPage,
  DOCS_ERRORS_TEST_IDS,
  PINNED_REASON_CODES,
} from "./errors-page";

// the curated Troubleshooting hub
export {
  TroubleshootingPage,
  TROUBLESHOOTING_PAGE_TEST_IDS,
  REPLAN_EVENTS_NOT_EXPOSED,
} from "./troubleshooting-page";

// the vocabulary Reference page
export { ReferencePage, REFERENCE_PAGE_TEST_IDS } from "./reference-page";

// the shared local helpers (link resolution, chrome, the term filter)
export {
  DOCS_SECTIONS,
  consoleRouteHref,
  docsLinkHref,
  getDocsSection,
  matchesDocsTerm,
  DocsLink,
  DocsPageFrame,
  DocsSection,
  MethodChip,
} from "./docs-shared";

// the contextual return path (?from=) and the route-local search
export {
  DocsContextBar,
  DocsContextSlot,
  DOCS_RETURN_PATH_TEST_ID,
  isLinkableFromPath,
} from "./docs-context";
export { DocsSearch, DOCS_SEARCH_TEST_ID } from "./docs-search";
