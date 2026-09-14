/**
 * Shared object-view helpers — the scaffolding contracts Workers 2/3 fill.
 *
 * The console renders backend resources through ONE object-inspection
 * vocabulary (spec: "reusable object inspector, activity, status, evidence,
 * JSON and API-request components"). These helpers describe HOW a resource
 * decomposes into sections/fields; they never hold or transform domain
 * state (the backend remains the single authority — refresh always
 * re-fetches truth).
 */

import type { ReactNode } from "react";

/** One labeled key/value row in an object's property grid. */
export interface ObjectField {
  /** Canonical backend member name (shown verbatim in mono). */
  label: string;
  /** The rendered value (string, or a richer node like Status/JsonViewer). */
  value: ReactNode;
  /** Optional one-line explanation of the member's semantics. */
  hint?: string;
}

/** One section of an object detail page (identity, lifecycle, plan, ...). */
export interface ObjectViewSection {
  id: string;
  title: string;
  fields: ObjectField[];
  /** Optional JSON payload the inspector renders for this section. */
  json?: unknown;
}

/** A cross-reference to another console object (deep link). */
export interface ObjectReference {
  kind: string;
  id: string;
  href: string;
  label?: string;
}

/** A timeline entry derived from backend activity/records. */
export interface ObjectActivityEntry {
  id: string;
  title: string;
  time?: string;
  description?: string;
  tone?: string;
}

/*
 * CONTRACTS FOR WORKERS 2/3 (to implement in their feature folders):
 *
 * 1. `buildContractSections(contract: Contract): ObjectViewSection[]`
 *    — identity, lifecycle, requirements/constraints, eligibility,
 *      plan, execution, assurance, evidence lineage, replanning history.
 *
 * 2. `buildLeaseSections(lease: Lease): ObjectViewSection[]`
 *    — identity, validity window, state (Status vocabulary), contract ref.
 *
 * 3. `buildWebhookEndpointSections(endpoint: WebhookEndpoint): ObjectViewSection[]`
 *    — identity, url, event types, deliveries ref.
 *
 * 4. `typedReferenceField(ref: OpaqueReference): ObjectField`
 *    — renders {ref_kind, value, provenance} with provenance visible.
 *
 * Render with: ObjectHeader + sections as property grids + Timeline for
 * activity + JsonViewer for raw payloads + ApiRequestPanel for the request
 * that produced the object.
 */
