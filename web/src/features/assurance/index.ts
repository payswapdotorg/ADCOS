/**
 * Assurance feature (Worker 3 — plan Task 8: assurance state).
 *
 * Supported contract objectives (latency, availability, capacity, provider
 * health) are the OBLIGATION REFERENCES the backend returns — opaque
 * typed references with their provenance, linked to their contract and
 * to the evidence chain (the demonstration runs&apos; attestation
 * records by contract_ref). NO metric dashboards are invented: the
 * assurance authority owns the semantics; this console renders the
 * references VERBATIM.
 */

export const ASSURANCE_FEATURE = {
  area: "assurance",
  route: "/assurance",
  owner: "worker-3",
  hardRule:
    "obligations render as the opaque references the backend returns — never invented metric dashboards",
} as const;

export { AssuranceView, ASSURANCE_VIEW_TEST_IDS } from "./assurance-view";
export {
  ObligationRef,
  OBLIGATION_REF_TEST_ID,
} from "./obligation-ref";
export { VerbatimNote } from "./verbatim-note";
