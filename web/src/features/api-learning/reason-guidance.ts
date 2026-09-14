/**
 * The canonical reason-code TROUBLESHOOTING GUIDANCE table.
 *
 * The DEC-0128 program, Task 7 of the frozen plan (the V2 learning
 * experience design §17 truth-and-disclosure + the Errors experience
 * group): the error workbench's ADDITIONAL, clearly-labelled guidance
 * section. The table maps the KNOWN canonical reason codes — exactly the
 * vocabulary of `@/lib/api/errors`' REASON_PRESENTATION map — to human
 * guidance structured as the frozen anatomy: what happened / why /
 * affected resource / next action / API reproduction / learn more.
 *
 * Honesty rules (non-negotiable #6/§17):
 * - the guidance NEVER replaces the verbatim backend reason: the
 *   workbench's V1 anatomy surfaces (message, reason chips, resource,
 *   curl) stay byte-identical and this section is purely additional;
 * - ONLY codes that exist in the canonical errors module appear here —
 *   the module-load guard below fails at import time if a key drifts
 *   outside the canonical vocabulary;
 * - unknown codes render NO guidance section at all — the V1 honest
 *   unknown treatment stands unchanged (never invented semantics);
 * - `relatedConcepts` ids must exist in the education registry's concept
 *   vocabulary (guarded at load time too).
 */

import { AdcosApiError, describeError } from "@/lib/api/errors";
import { getConcept } from "@/lib/education";

/** The six-part guidance anatomy for one canonical reason code. */
export interface ReasonTroubleshootingGuidance {
  /** The canonical reason code (verbatim — this table's key). */
  code: string;
  /** What happened — the human-readable summary of the failure class. */
  whatHappened: string;
  /** Why it happens — the mechanism behind the code. */
  why: string;
  /** Which resource/subject the code is about. */
  affectedResource: string;
  /** The concrete next action(s) to take. */
  nextAction: string;
  /** How to reproduce or verify the condition through the real API. */
  apiReproduction: string;
  /** Education-registry concept ids that deepen the diagnosis. */
  relatedConcepts: string[];
}

/**
 * Does this code exist in the canonical errors module? Derived through
 * the module's own public `describeError` API (the map is private — the
 * same derivation discipline the docs Errors page follows): a known code
 * yields its canonical title, an unknown one yields the module's
 * "Request failed" fallback title.
 */
export function isCanonicalReasonCode(code: string): boolean {
  const presentation = describeError(
    new AdcosApiError({
      status: 400,
      reason: code,
      message: "",
      request: { method: "GET", path: "(reason-guidance)" },
    }),
  );
  return presentation.title !== "Request failed";
}

/** The canonical title for a known code (rendered next to the code chip). */
export function canonicalReasonTitle(code: string): string {
  return describeError(
    new AdcosApiError({
      status: 400,
      reason: code,
      message: "",
      request: { method: "GET", path: "(reason-guidance)" },
    }),
  ).title;
}

/**
 * The troubleshooting guidance table — one entry per canonical reason
 * code of `@/lib/api/errors` (32 codes; the docs Errors page pins the
 * same vocabulary). Every sentence explains the code; none rewrites it.
 */
export const REASON_TROUBLESHOOTING: ReasonTroubleshootingGuidance[] = [
  /* -------- authentication & capability -------- */
  {
    code: "authentication-invalid",
    whatHappened: "The boundary rejected the application's credential.",
    why: "The application id and credential pair does not match an active application — a wrong id, a malformed credential, or an application that is no longer active.",
    affectedResource: "The authenticated identity this session presents on every developer-API request (X-ADCOS-Application / X-ADCOS-Credential).",
    nextAction: "Re-check the application id and credential in the session menu and reconnect with a freshly issued credential.",
    apiReproduction: "GET /api/2.0/application with the same headers reproduces the 401 envelope exactly — the captured anatomy above is the verbatim original.",
    relatedConcepts: ["application-capability"],
  },
  {
    code: "authentication-expired",
    whatHappened: "The credential's validity window has passed.",
    why: "Credentials are issued with a validity window; this one is past it, so the boundary refuses it even though the application itself may still exist.",
    affectedResource: "The session's credential (not necessarily the application).",
    nextAction: "Obtain a freshly issued credential and reconnect (Settings → Session → Connect application).",
    apiReproduction: "Re-issuing any authenticated request repeats the failure; application_self is the lightest probe.",
    relatedConcepts: ["application-capability"],
  },
  {
    code: "environment-mismatch",
    whatHappened: "The credential was not issued for this runtime's environment.",
    why: "Credentials are issued per environment; the boundary refuses a credential presented against a different environment, even when it is otherwise valid.",
    affectedResource: "The session's credential/environment pairing.",
    nextAction: "Use a credential issued for the environment this runtime reports (readyz carries it).",
    apiReproduction: "GET /api/2.0/application shows the mismatch envelope; GET /readyz shows the runtime's own environment.",
    relatedConcepts: ["application-capability", "policy"],
  },
  {
    code: "capability-denied",
    whatHappened: "The connected application lacks the capability grant this operation requires.",
    why: "Capability grants unlock operations; the authenticated application's grant list does not include the one this operation's registry entry demands.",
    affectedResource: "The application's capability list (the Developers workspace and application_self both show it).",
    nextAction: "Inspect the granted capabilities, then use an application that holds the required grant for this operation.",
    apiReproduction: "application_self returns the capability list verbatim; re-running the operation reproduces the denial verbatim.",
    relatedConcepts: ["application-capability", "policy"],
  },
  /* -------- request shape & transport -------- */
  {
    code: "version-unsupported",
    whatHappened: "The request's API version does not match the route's.",
    why: "The route version and the X-ADCOS-API-Version header must agree — the developer boundary is 2.0.",
    affectedResource: "The request's versioning header against its route.",
    nextAction: "Send X-ADCOS-API-Version: 2.0 on /api/2.0 routes — the console's typed client does this automatically on every request.",
    apiReproduction: "The Explorer's request-headers table shows the version header the console itself sends.",
    relatedConcepts: ["application-capability"],
  },
  {
    code: "rate-limited",
    whatHappened: "The request exceeded the application's rate limit.",
    why: "The boundary enforces per-application rate limits; this request arrived while the window was exhausted, and the reset instant is carried in the envelope.",
    affectedResource: "The application's rate-limit window (the envelope's rate_limit surface: limit, remaining, reset_at).",
    nextAction: "Wait for rate_limit.reset_at, then retry — the backend marks this error retryable, so the workbench offers the re-issue.",
    apiReproduction: "The captured envelope's rate_limit members are the exact numbers; re-issuing after the reset instant succeeds.",
    relatedConcepts: ["application-capability", "policy"],
  },
  {
    code: "payload-too-large",
    whatHappened: "The request body exceeds the boundary's 1 MiB cap.",
    why: "The boundary rejects oversized bodies before parsing — the cap is fixed, not negotiated.",
    affectedResource: "The request body's size.",
    nextAction: "Reduce the body under the cap; canonical material is opaque references by design and stays small.",
    apiReproduction: "Re-sending the same body reproduces the rejection at the same size.",
    relatedConcepts: ["policy"],
  },
  {
    code: "malformed-json",
    whatHappened: "The request body was not valid JSON.",
    why: "The boundary parses every body as JSON before validation; this one failed at the parse step, so no member was ever read.",
    affectedResource: "The request body's bytes (nothing was interpreted).",
    nextAction: "Fix the JSON syntax and re-send — the Explorer's local validation reports this before the request ever leaves the browser.",
    apiReproduction: "The curl reproduction below carries the exact bytes; correcting them and re-sending is the reproduction.",
    relatedConcepts: [],
  },
  {
    code: "invalid-request-body",
    whatHappened: "The request body must be a JSON object.",
    why: "The boundary requires a top-level JSON object for this method; an array, a scalar or an empty non-object body is refused before member validation.",
    affectedResource: "The request body's top-level shape.",
    nextAction: "Send a JSON object ({...}) as the body.",
    apiReproduction: "Re-send with an object body — the same request otherwise identical succeeds the shape check.",
    relatedConcepts: [],
  },
  {
    code: "invalid-input",
    whatHappened: "A member of the request body failed validation.",
    why: "The backend validated the body against the operation's required members and frozen vocabularies; the captured message names the offending member.",
    affectedResource: "The request-body member the backend's message names.",
    nextAction: "Fix the named member and re-issue — the backend's message is the authority on what was wrong, never a guess.",
    apiReproduction: "The Explorer carries the operation's editable example body; correcting the member there and executing is the live reproduction.",
    relatedConcepts: ["policy"],
  },
  {
    code: "temporal-invalid",
    whatHappened: "The request's instants are invalid.",
    why: "Temporal members must be RFC 3339 UTC instants with a sane ordering — a malformed instant, or not_before after not_after, is refused.",
    affectedResource: "The temporal members of the request (validity windows, recorded_at, lease windows).",
    nextAction: "Check that the instants parse as RFC 3339 UTC and that the windows are correctly ordered.",
    apiReproduction: "Re-sending the same body reproduces the rejection; the same request with corrected instants passes.",
    relatedConcepts: ["connectivity-contract"],
  },
  {
    code: "secret-rejected",
    whatHappened: "The backend's secret scan rejected the material.",
    why: "Secret-like values in request bodies are refused — ADCOS stores no secrets inside contract material.",
    affectedResource: "The rejected body member carrying the secret-like value.",
    nextAction: "Remove the secret-like value and use an opaque reference instead.",
    apiReproduction: "Re-send the body without the secret-like value through the same operation.",
    relatedConcepts: ["policy", "application-capability"],
  },
  {
    code: "vocabulary",
    whatHappened: "A member used a value outside its frozen vocabulary.",
    why: "Constraint kinds, termination conditions and event types come from frozen vocabularies; this value is not in the one governing the member.",
    affectedResource: "The named member whose value was refused.",
    nextAction: "Use the frozen vocabulary's own values — the docs Reference page lists the vocabularies verbatim.",
    apiReproduction: "Re-send with a vocabulary value; the refused value is in the captured message.",
    relatedConcepts: ["policy"],
  },
  /* -------- routing & resources -------- */
  {
    code: "route-unknown",
    whatHappened: "The requested route does not exist on the accepted boundary.",
    why: "The boundary is a fixed route table — exactly the coverage registry's 25 operations; this method+path combination is outside it.",
    affectedResource: "The request's method and path.",
    nextAction: "Re-issue from the surface that made the request after a refresh — the console only calls registry-backed routes. Verify the real method and path on the API documentation pages.",
    apiReproduction: "The exact method+path is in the anatomy above; comparing it against the API documentation is the verification.",
    relatedConcepts: [],
  },
  {
    code: "resource-unknown",
    whatHappened: "The addressed resource id resolves to nothing this application can see.",
    why: "Either the id has never existed, or it exists under a different application — reads are scoped to the authenticated principal.",
    affectedResource: "The path-parameter resource id of the request.",
    nextAction: "Re-check the identifier against the owning list read (contracts_list, leases_list or endpoints_list) — those enumerate exactly the ids this application can see.",
    apiReproduction: "Run the list read, then the same read with an id it returns; the contrast is the reproduction.",
    relatedConcepts: ["connectivity-contract"],
  },
  {
    code: "unknown-contract",
    whatHappened: "The contract id in the request resolves to no visible contract.",
    why: "The canonical subsystem reason behind a resource-shaped 404 on the contract routes — the boundary adapts it to resource-unknown on the developer surface, and both codes render verbatim.",
    affectedResource: "The contract id riding the request path.",
    nextAction: "Re-check the contract id against contracts_list — the contract either does not exist or belongs to another application.",
    apiReproduction: "contracts_list followed by contract_get with a listed id reproduces the working lookup chain.",
    relatedConcepts: ["connectivity-contract"],
  },
  /* -------- contract & object state machine -------- */
  {
    code: "invalid-transition",
    whatHappened: "The object's current state does not permit this command.",
    why: "Contracts and leases move through a frozen state machine; the command is legal only from specific states (activation requires OFFER_SELECTED, termination requires a non-terminal contract).",
    affectedResource: "The object's current state — read it back before commanding it again.",
    nextAction: "Refresh the owning surface to see the object's current state, then choose the command that state permits.",
    apiReproduction: "The lifecycle observation (intent_lifecycle) reports the current state verbatim; re-running the command shows the verbatim rejection again.",
    relatedConcepts: ["connectivity-contract", "policy", "eligibility"],
  },
  {
    code: "invalid-state",
    whatHappened: "The object's state makes this operation illegal right now.",
    why: "The state machine's position — not the request's shape — is what refuses the operation.",
    affectedResource: "The object's state.",
    nextAction: "Refresh to see the object's current state; the operation becomes legal from the state it expects.",
    apiReproduction: "Read the object back, then re-issue the same request — the state, not the request, decides.",
    relatedConcepts: ["connectivity-contract", "fulfillment"],
  },
  {
    code: "contract-terminal",
    whatHappened: "The contract is in a terminal state.",
    why: "Terminated contracts accept no further commands — terminal is final by design; only the reads still answer.",
    affectedResource: "The contract itself.",
    nextAction: "Record a new intent if connectivity is still needed; nothing can revive a terminal contract.",
    apiReproduction: "intent_lifecycle shows the terminal state; every command on the id answers with this same code.",
    relatedConcepts: ["connectivity-contract"],
  },
  {
    code: "constraint-immutable",
    whatHappened: "Hard constraints cannot be changed after creation.",
    why: "Immutability is what makes hard constraints safe to compose over — every replan re-verifies candidates against them, never weakening them.",
    affectedResource: "The contract's hard_constraints member.",
    nextAction: "Record a new contract carrying the constraints you need; the existing one keeps its own, verbatim.",
    apiReproduction: "The contract read shows the recorded constraints verbatim — they are the material the verification gate uses.",
    relatedConcepts: ["connectivity-contract", "replan-failover"],
  },
  {
    code: "not-yet-valid",
    whatHappened: "The validity window has not opened yet.",
    why: "Contracts and leases are answerable only inside their not_before/not_after window; the current instant is before not_before.",
    affectedResource: "The object's validity window.",
    nextAction: "Wait for the window to open, or record an object whose window opens now.",
    apiReproduction: "The object's read carries its validity window; re-issuing after not_before passes.",
    relatedConcepts: ["connectivity-contract"],
  },
  {
    code: "expired",
    whatHappened: "The validity window has closed.",
    why: "The object's not_after instant has passed — the window does not reopen.",
    affectedResource: "The object's validity window.",
    nextAction: "For leases, renew into a new window (lease_renew); otherwise record a new object.",
    apiReproduction: "The object's read carries the expired window; renewal with a future window is the working contrast.",
    relatedConcepts: ["connectivity-contract"],
  },
  {
    code: "sequence-conflict",
    whatHappened: "An identical creation core already exists.",
    why: "The durable journal rejects a duplicate creation whose core material matches an existing object — a conflict, not a silent second object.",
    affectedResource: "The existing object carrying the same creation core.",
    nextAction: "Inspect the current state of the existing object instead of re-creating it.",
    apiReproduction: "The owning list read finds the existing object; its read is the continuation.",
    relatedConcepts: ["connectivity-contract"],
  },
  {
    code: "replay-stale",
    whatHappened: "The replayed sequence was rejected as stale.",
    why: "The durable journal rejected this sequence position — the replayed command no longer matches the journal's head.",
    affectedResource: "The command's journal position.",
    nextAction: "Refresh and inspect the object's current state before re-issuing the command.",
    apiReproduction: "Read the object back, then re-issue the command as a fresh mutation with a fresh idempotency key.",
    relatedConcepts: ["connectivity-contract"],
  },
  /* -------- pagination & filters -------- */
  {
    code: "pagination-invalid",
    whatHappened: "The list request's pagination parameters are invalid.",
    why: "The cursor or limit is invalid for this list context — a limit outside 1..100, or a malformed (stale) cursor.",
    affectedResource: "The list request's body (its limit/cursor members).",
    nextAction: "Reload the list — the console's default-page read needs no cursor; page forward only with the cursor the previous response carried.",
    apiReproduction: "The canonical GET-body form rides the reproduction below; sending it with a valid limit/cursor pair is the working contrast.",
    relatedConcepts: [],
  },
  {
    code: "filter-invalid",
    whatHappened: "The list request's filter member is invalid.",
    why: "Filters are declared per list context — contracts and leases filter by state; anything else is refused.",
    affectedResource: "The list request's filters member.",
    nextAction: "Use a declared filter member (a state filter on the contracts or leases list).",
    apiReproduction: "Re-send the same list read with the declared filter; the shape is in the list surfaces' canonical form.",
    relatedConcepts: [],
  },
  /* -------- idempotency -------- */
  {
    code: "idempotency-key-required",
    whatHappened: "The mutation carried no idempotency key.",
    why: "Every mutation requires X-ADCOS-Idempotency-Key — the boundary's replay protection; the request was refused before any effect.",
    affectedResource: "The mutation request's headers.",
    nextAction: "Retry — the console's typed client sends one automatically. Outside the console, send a fresh key with every new mutation.",
    apiReproduction: "The Explorer pins and displays the key per mutation; the curl reproduction carries it as a header line.",
    relatedConcepts: ["application-capability", "policy"],
  },
  {
    code: "idempotency-conflict",
    whatHappened: "This idempotency key was already used with a different body.",
    why: "A key binds to the first body it saw — replaying it with a different body is a conflict, never a silent success.",
    affectedResource: "The mutation request's key/body pairing.",
    nextAction: "Use a new key for a new mutation; replaying the same key with the same body returns the original response byte-identically.",
    apiReproduction: "The Explorer's Replay re-sends the recorded key and body byte-identically — the exact contrast between replay and conflict.",
    relatedConcepts: ["application-capability", "policy"],
  },
  /* -------- runtime & durability -------- */
  {
    code: "backend-unreachable",
    whatHappened: "The request never reached the ADCOS runtime.",
    why: "The transport itself failed (network, DNS or proxy) — this code is synthesized client-side by the typed client and labeled as such, never presented as a backend reason.",
    affectedResource: "The console-to-runtime connection (same-origin; in dev the Next rewrite proxies to ADCOS_BACKEND_URL).",
    nextAction: "Verify the runtime is up: the shell's environment indicator polls /readyz, and Settings shows the full readiness document. The workbench offers the re-issue once it recovers.",
    apiReproduction: "GET /readyz is a platform surface — it answers independently of authentication and locates a degraded consumed backend.",
    relatedConcepts: ["application-capability"],
  },
  {
    code: "internal-error",
    whatHappened: "The runtime failed unexpectedly.",
    why: "An unexpected server-side failure — not caused by the request's shape or content.",
    affectedResource: "The runtime's own state, not the request.",
    nextAction: "Retry once; if it persists, escalate to the platform operator carrying the request id from the anatomy.",
    apiReproduction: "The request id in the anatomy is the correlation handle — re-issuing the identical request either reproduces it or clears it.",
    relatedConcepts: [],
  },
  {
    code: "store-failed",
    whatHappened: "The durable store failed the operation.",
    why: "The runtime's persistence layer failed while serving the request — a platform-level condition.",
    affectedResource: "The runtime's durable store.",
    nextAction: "Retry; if it persists, escalate — the store's recovery decides whether the same request later succeeds.",
    apiReproduction: "Re-issuing the same request after the store recovers is the natural reproduction contrast.",
    relatedConcepts: [],
  },
  {
    code: "journal-tamper",
    whatHappened: "The durable journal failed integrity verification.",
    why: "The journal's verification gate rejected the record — a serious platform-level integrity condition, never a client-side problem.",
    affectedResource: "The runtime's durable journal.",
    nextAction: "Escalate to the platform operator immediately with the request id; do not keep issuing mutations against this runtime.",
    apiReproduction: "The request id correlates the attempt; the operator's side of the journal is where this is investigated.",
    relatedConcepts: [],
  },
];

/* ------------------------------------------------------------------ *
 * The module-load guards (fail loudly BEFORE any UI renders)
 * ------------------------------------------------------------------ */

{
  const seen = new Set<string>();
  for (const entry of REASON_TROUBLESHOOTING) {
    if (seen.has(entry.code)) {
      throw new Error(
        `reason-guidance duplicates code "${entry.code}" — one guidance entry per canonical reason code`,
      );
    }
    seen.add(entry.code);
    if (!isCanonicalReasonCode(entry.code)) {
      throw new Error(
        `reason-guidance references non-canonical code "${entry.code}" — only @/lib/api/errors' own vocabulary is guidable`,
      );
    }
    for (const conceptId of entry.relatedConcepts) {
      if (!getConcept(conceptId)) {
        throw new Error(
          `reason-guidance references unknown concept "${conceptId}" on code "${entry.code}" — the education registry is the only concept authority`,
        );
      }
    }
  }
}

/** Look up one code's guidance — `undefined` for unknown codes BY DESIGN. */
export function getReasonTroubleshooting(code: string): ReasonTroubleshootingGuidance | undefined {
  return REASON_TROUBLESHOOTING.find((entry) => entry.code === code);
}

/**
 * The guidance for a captured error's OWN codes: the boundary `reason`
 * first; when that is not canonical but the backend adapted a
 * `canonical_reason` that is, the canonical code selects the guidance.
 * Mirrors the V1 `reasonGuidanceForCodes` resolution shape (both codes
 * still render verbatim wherever they appear — this lookup only picks
 * the guidance entry, it never rewrites a code).
 */
export function reasonTroubleshootingForCodes(
  reason: string,
  canonicalReason: string | null,
): ReasonTroubleshootingGuidance | undefined {
  const fromReason = getReasonTroubleshooting(reason);
  if (fromReason) return fromReason;
  if (canonicalReason && canonicalReason !== reason) {
    return getReasonTroubleshooting(canonicalReason) ?? undefined;
  }
  return undefined;
}

/** The learn-more hrefs rendered with one guidance entry. */
export function reasonLearnMoreHrefs(guidance: ReasonTroubleshootingGuidance): { href: string; label: string }[] {
  return [
    { href: `/docs/errors#code-${guidance.code}`, label: "The reason-code reference" },
    { href: "/docs/troubleshooting", label: "Troubleshooting paths" },
    ...guidance.relatedConcepts.map((conceptId) => ({
      href: `/docs/concepts/${conceptId}`,
      label: getConcept(conceptId)?.term ?? conceptId,
    })),
  ];
}
