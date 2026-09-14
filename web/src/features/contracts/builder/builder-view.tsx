"use client";
import "@/features/eligibility/fetch-binding-shim";

/**
 * BuilderView — the connectivity-intent builder (Worker 2, plan Task 5):
 *
 * - GUIDED mode: fields map 1:1 to the canonical members (each labeled
 *   with the canonical name in mono); defaults seed from the canonical
 *   demo body; hard-constraint params are free-form typed mappings that
 *   serialize byte-equal (the number heuristic only);
 * - ADVANCED mode: the canonical JSON body edited directly, with live
 *   JSON.parse validation feedback; members the guided form does not
 *   represent are PRESERVED and merged back on submit;
 * - the "View API request" section is ALWAYS visible near the submit
 *   button: the exact POST /api/2.0/intents request (headers including
 *   the idempotency key generated ONCE for this form instance, and the
 *   exact serialized body) both as the interactive panel and as full JSON
 *   text;
 * - client-side checks are convenience only — the backend is the
 *   validation authority and its verbatim reason codes surface through
 *   ErrorState on rejection.
 */

import { useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { CreateIntentInput } from "@/lib/api/types";
import { ApiRequestPanel, CodeBlock, ErrorState } from "@/components/ui";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import { ConnectGuidance } from "../connect-guidance";
import {
  buildIntentBody,
  canonicalIntentBody,
  defaultGuidedState,
  parseAdvancedToGuided,
  validateGuidedState,
  type GuidedBuilderState,
  type GuidedConstraintDraft,
  type GuidedRefDraft,
} from "./serialization";

const inputClasses =
  "h-8 rounded-md border border-line bg-raised px-2 text-sm text-ink";

const monoInputClasses = `${inputClasses} font-mono`;

const removeButtonClasses =
  "inline-flex h-7 shrink-0 items-center rounded-md border border-line px-2 text-xs text-ink-muted transition-colors hover:text-ink";

const addButtonClasses =
  "inline-flex h-7 items-center self-start rounded-md border border-line px-2 text-xs text-ink-muted transition-colors hover:text-ink";

/** A labeled canonical member block (member name in mono + a short hint). */
function MemberField({
  member,
  hint,
  children,
}: {
  member: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <code className="rounded border border-line-strong px-1.5 py-px font-mono text-2xs text-ink">
          {member}
        </code>
        {hint ? <span className="text-xs text-ink-faint">{hint}</span> : null}
      </div>
      {children}
    </div>
  );
}

/** The requirement / assurance-obligation row editor. */
function RefDraftRows({
  labelPrefix,
  drafts,
  onChange,
  addLabel,
  addAriaLabel,
}: {
  labelPrefix: string;
  drafts: GuidedRefDraft[];
  onChange: (drafts: GuidedRefDraft[]) => void;
  addLabel: string;
  addAriaLabel: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-col gap-2">
        {drafts.map((draft, index) => (
          <li
            key={`${labelPrefix}-${index}`}
            className="flex flex-wrap items-center gap-2 rounded-md border border-line bg-raised px-2.5 py-2"
          >
            <input
              aria-label={`${labelPrefix} ${index + 1} value`}
              value={draft.value}
              onChange={(event) =>
                onChange(
                  drafts.map((item, itemIndex) =>
                    itemIndex === index
                      ? { ...item, value: event.target.value }
                      : item,
                  ),
                )
              }
              placeholder="value"
              className={`${monoInputClasses} min-w-[13rem] flex-1`}
            />
            <input
              aria-label={`${labelPrefix} ${index + 1} issuer`}
              value={draft.issuer}
              onChange={(event) =>
                onChange(
                  drafts.map((item, itemIndex) =>
                    itemIndex === index
                      ? { ...item, issuer: event.target.value }
                      : item,
                  ),
                )
              }
              placeholder="issuer"
              className={`${monoInputClasses} w-40`}
            />
            <input
              aria-label={`${labelPrefix} ${index + 1} decision_refs (comma-separated)`}
              value={draft.decisionRefs}
              onChange={(event) =>
                onChange(
                  drafts.map((item, itemIndex) =>
                    itemIndex === index
                      ? { ...item, decisionRefs: event.target.value }
                      : item,
                  ),
                )
              }
              placeholder="decision_refs (comma-separated)"
              className={`${monoInputClasses} w-60`}
            />
            <button
              type="button"
              aria-label={`Remove ${labelPrefix} ${index + 1}`}
              onClick={() => onChange(drafts.filter((_, i) => i !== index))}
              className={removeButtonClasses}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        aria-label={addAriaLabel}
        onClick={() => onChange([...drafts, { value: "", issuer: "", decisionRefs: "" }])}
        className={addButtonClasses}
      >
        {addLabel}
      </button>
    </div>
  );
}

/** The plain typed-reference row editor (service properties, scope). */
function ValueDraftRows({
  labelPrefix,
  drafts,
  onChange,
  addLabel,
  addAriaLabel,
}: {
  labelPrefix: string;
  drafts: { value: string }[];
  onChange: (drafts: { value: string }[]) => void;
  addLabel: string;
  addAriaLabel: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-col gap-2">
        {drafts.map((draft, index) => (
          <li
            key={`${labelPrefix}-${index}`}
            className="flex flex-wrap items-center gap-2 rounded-md border border-line bg-raised px-2.5 py-2"
          >
            <input
              aria-label={`${labelPrefix} ${index + 1} value`}
              value={draft.value}
              onChange={(event) =>
                onChange(
                  drafts.map((item, itemIndex) =>
                    itemIndex === index
                      ? { ...item, value: event.target.value }
                      : item,
                  ),
                )
              }
              placeholder="value"
              className={`${monoInputClasses} min-w-[13rem] flex-1`}
            />
            <button
              type="button"
              aria-label={`Remove ${labelPrefix} ${index + 1}`}
              onClick={() => onChange(drafts.filter((_, i) => i !== index))}
              className={removeButtonClasses}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        aria-label={addAriaLabel}
        onClick={() => onChange([...drafts, { value: "" }])}
        className={addButtonClasses}
      >
        {addLabel}
      </button>
    </div>
  );
}

/** The hard-constraint editor (kind select + free-form typed params). */
function ConstraintEditor({
  draft,
  index,
  onChange,
  onRemove,
}: {
  draft: GuidedConstraintDraft;
  index: number;
  onChange: (draft: GuidedConstraintDraft) => void;
  onRemove: () => void;
}) {
  return (
    <li className="flex flex-col gap-2 rounded-md border border-line bg-raised px-2.5 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor={`constraint-${index}-kind`}>
          Constraint {index + 1} kind
        </label>
        <select
          id={`constraint-${index}-kind`}
          value={draft.kindIsCustom ? "__custom__" : draft.kind}
          onChange={(event) =>
            onChange({
              ...draft,
              kindIsCustom: event.target.value === "__custom__",
              kind: event.target.value === "__custom__" ? "" : event.target.value,
            })
          }
          className={`${inputClasses} bg-surface`}
        >
          <option value="latency-bound">latency-bound</option>
          <option value="throughput-floor">throughput-floor</option>
          <option value="__custom__">custom…</option>
        </select>
        {draft.kindIsCustom ? (
          <input
            aria-label={`Constraint ${index + 1} custom kind`}
            value={draft.kind}
            onChange={(event) => onChange({ ...draft, kind: event.target.value })}
            placeholder="kind"
            className={`${monoInputClasses} w-44`}
          />
        ) : null}
        <button
          type="button"
          aria-label={`Remove constraint ${index + 1}`}
          onClick={onRemove}
          className={removeButtonClasses}
        >
          Remove
        </button>
      </div>
      <div className="flex flex-col gap-1.5">
        {draft.params.map((row, rowIndex) => (
          <div key={`constraint-${index}-param-${rowIndex}`} className="flex flex-wrap items-center gap-2">
            <input
              aria-label={`Constraint ${index + 1} param ${rowIndex + 1} key`}
              value={row.key}
              onChange={(event) =>
                onChange({
                  ...draft,
                  params: draft.params.map((item, i) =>
                    i === rowIndex ? { ...item, key: event.target.value } : item,
                  ),
                })
              }
              placeholder="param key"
              className={`${monoInputClasses} w-40`}
            />
            <span aria-hidden="true" className="font-mono text-xs text-ink-faint">
              :
            </span>
            <input
              aria-label={`Constraint ${index + 1} param ${rowIndex + 1} value`}
              value={row.value}
              onChange={(event) =>
                onChange({
                  ...draft,
                  params: draft.params.map((item, i) =>
                    i === rowIndex ? { ...item, value: event.target.value } : item,
                  ),
                })
              }
              placeholder="param value"
              className={`${monoInputClasses} w-40`}
            />
            <button
              type="button"
              aria-label={`Remove constraint ${index + 1} param ${rowIndex + 1}`}
              onClick={() =>
                onChange({
                  ...draft,
                  params: draft.params.filter((_, i) => i !== rowIndex),
                })
              }
              className={removeButtonClasses}
            >
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          aria-label={`Add param to constraint ${index + 1}`}
          onClick={() => onChange({ ...draft, params: [...draft.params, { key: "", value: "" }] })}
          className={addButtonClasses}
        >
          Add param
        </button>
      </div>
    </li>
  );
}

/* ------------------------------------------------------------------ */
/* The builder view                                                    */
/* ------------------------------------------------------------------ */

export function BuilderView() {
  const { status, client, application } = useSession();
  const router = useRouter();
  const connected = status === "connected";

  const [mode, setMode] = useState<"guided" | "advanced">("guided");
  const [state, setState] = useState<GuidedBuilderState>(defaultGuidedState);
  const [preserved, setPreserved] = useState<Record<string, unknown>>({});
  const [advancedText, setAdvancedText] = useState(() =>
    JSON.stringify(canonicalIntentBody(), null, 2),
  );
  const [switchError, setSwitchError] = useState<string | null>(null);
  const [validation, setValidation] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  // generated ONCE per form instance — the preview and the request sent
  // carry the same X-ADCOS-Idempotency-Key
  const [idempotencyKey] = useState(() => crypto.randomUUID());

  const advancedParse = useMemo(() => {
    try {
      return { ok: true as const, value: JSON.parse(advancedText) as unknown };
    } catch (error) {
      return {
        ok: false as const,
        message: error instanceof Error ? error.message : String(error),
      };
    }
  }, [advancedText]);

  const bodyIsObject =
    mode === "guided" ||
    (advancedParse.ok &&
      typeof advancedParse.value === "object" &&
      advancedParse.value !== null &&
      !Array.isArray(advancedParse.value));

  const body: unknown =
    mode === "guided"
      ? buildIntentBody(state, preserved)
      : advancedParse.ok
        ? advancedParse.value
        : advancedText;

  const headers = [
    { name: "X-ADCOS-Application", value: application?.application_id ?? "" },
    { name: "X-ADCOS-API-Version", value: "2.0" },
    { name: "X-ADCOS-Idempotency-Key", value: idempotencyKey },
  ];

  function switchToGuided() {
    if (!advancedParse.ok) {
      setSwitchError(`Fix the JSON before switching to guided mode: ${advancedParse.message}`);
      return;
    }
    const parsed = parseAdvancedToGuided(advancedParse.value);
    if (!parsed) {
      setSwitchError("The canonical body must be a JSON object.");
      return;
    }
    setState(parsed.state);
    setPreserved(parsed.preserved);
    setMode("guided");
    setSwitchError(null);
  }

  function switchToAdvanced() {
    setAdvancedText(JSON.stringify(buildIntentBody(state, preserved), null, 2));
    setMode("advanced");
    setSwitchError(null);
  }

  async function handleSubmit() {
    if (pending) return;
    setSubmitError(null);
    if (mode === "guided") {
      const problem = validateGuidedState(state);
      if (problem) {
        setValidation(problem);
        return;
      }
    } else {
      if (!advancedParse.ok) {
        setValidation(`Invalid JSON: ${advancedParse.message}`);
        return;
      }
      if (
        typeof advancedParse.value !== "object" ||
        advancedParse.value === null ||
        Array.isArray(advancedParse.value)
      ) {
        setValidation("The canonical body must be a JSON object.");
        return;
      }
    }
    setValidation(null);
    setPending(true);
    try {
      const envelope = await client.createIntent(body as CreateIntentInput, {
        idempotencyKey,
      });
      router.push(`/connectivity/contracts/${envelope.data.id}`);
    } catch (caught) {
      setSubmitError(caught);
    } finally {
      setPending(false);
    }
  }

  const header = (
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-ink">New connectivity intent</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Records a connectivity intent through POST /api/2.0/intents. Guided
          fields map 1:1 to the canonical members; advanced mode edits the
          canonical JSON directly.
        </p>
      </div>
      <Link
        href="/connectivity"
        className="inline-flex h-8 items-center rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface"
      >
        ← Connectivity
      </Link>
    </header>
  );

  if (!connected) {
    return (
      <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
        <div className="flex flex-col gap-4">
          {header}
          <ConnectGuidance lead="Recording an intent is an authenticated developer-API mutation (POST /api/2.0/intents with the session headers)." />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <div className="flex flex-col gap-5">
        {header}

        <div className="flex flex-wrap items-center gap-3">
          <div role="group" aria-label="Builder mode" className="flex gap-2">
            <button
              type="button"
              aria-pressed={mode === "guided"}
              onClick={() => {
                if (mode !== "guided") switchToGuided();
              }}
              className={cn(
                "h-8 rounded-md border px-3 text-sm transition-colors",
                mode === "guided"
                  ? "border-accent bg-raised text-ink"
                  : "border-line text-ink-muted hover:text-ink",
              )}
            >
              Guided
            </button>
            <button
              type="button"
              aria-pressed={mode === "advanced"}
              onClick={() => {
                if (mode !== "advanced") switchToAdvanced();
              }}
              className={cn(
                "h-8 rounded-md border px-3 text-sm transition-colors",
                mode === "advanced"
                  ? "border-accent bg-raised text-ink"
                  : "border-line text-ink-muted hover:text-ink",
              )}
            >
              Advanced (canonical JSON)
            </button>
          </div>
          {Object.keys(preserved).length > 0 ? (
            <p
              data-testid="preserved-members-notice"
              className="rounded-md border border-line bg-raised px-3 py-1.5 text-xs text-ink-muted"
            >
              {Object.keys(preserved).length} unknown member(s) preserved from advanced
              mode
            </p>
          ) : null}
        </div>
        {switchError ? (
          <p role="alert" className="text-sm text-danger">
            {switchError}
          </p>
        ) : null}

        {mode === "guided" ? (
          <form
            className="flex flex-col gap-5 rounded-md border border-line bg-surface px-4 py-4"
            onSubmit={(event) => {
              event.preventDefault();
              void handleSubmit();
            }}
          >
            <MemberField
              member="requirements"
              hint="Opaque typed references with provenance (ref_kind “intent-requirements”, fixed) — at least one is required."
            >
              <RefDraftRows
                labelPrefix="requirement"
                drafts={state.requirements}
                onChange={(requirements) => setState((prev) => ({ ...prev, requirements }))}
                addLabel="Add requirement"
                addAriaLabel="Add requirement"
              />
            </MemberField>

            <MemberField
              member="validity"
              hint="RFC 3339 UTC instants (YYYY-MM-DDTHH:MM:SSZ); not_after must be later than not_before."
            >
              <div className="flex flex-wrap gap-2">
                <input
                  aria-label="validity not_before"
                  value={state.validityNotBefore}
                  onChange={(event) =>
                    setState((prev) => ({ ...prev, validityNotBefore: event.target.value }))
                  }
                  className={`${monoInputClasses} w-60`}
                />
                <span aria-hidden="true" className="self-center font-mono text-xs text-ink-faint">
                  →
                </span>
                <input
                  aria-label="validity not_after"
                  value={state.validityNotAfter}
                  onChange={(event) =>
                    setState((prev) => ({ ...prev, validityNotAfter: event.target.value }))
                  }
                  className={`${monoInputClasses} w-60`}
                />
              </div>
            </MemberField>

            <MemberField
              member="termination"
              hint="conditions (comma-separated) and the compensation reference (ref_kind “compensation”, fixed)."
            >
              <div className="flex flex-col gap-2">
                <input
                  aria-label="termination conditions (comma-separated)"
                  value={state.terminationConditions}
                  onChange={(event) =>
                    setState((prev) => ({
                      ...prev,
                      terminationConditions: event.target.value,
                    }))
                  }
                  className={`${monoInputClasses} w-80`}
                />
                <input
                  aria-label="termination compensation value"
                  value={state.compensationValue}
                  onChange={(event) =>
                    setState((prev) => ({ ...prev, compensationValue: event.target.value }))
                  }
                  className={`${monoInputClasses} w-80`}
                />
              </div>
            </MemberField>

            <MemberField
              member="hard_constraints"
              hint="Immutable after creation; params are free-form typed mappings that serialize byte-equal (numeric-looking values become numbers)."
            >
              <div className="flex flex-col gap-2">
                {"hard_constraints" in preserved ? (
                  <div
                    data-testid="constraints-locked-notice"
                    className="rounded-md border border-dashed border-warning/60 bg-warning/5 px-3 py-2 text-sm text-ink-muted"
                  >
                    hard_constraints carry param types the guided editor
                    cannot represent byte-exactly (edited in advanced mode),
                    so they are preserved verbatim here and the guided editor
                    is locked — edit constraints in{" "}
                    <span className="font-mono text-xs">advanced mode</span>{" "}
                    to change them. Nothing is dropped or coerced.
                  </div>
                ) : (
                  <>
                    <ul className="flex flex-col gap-2">
                      {state.hardConstraints.map((draft, index) => (
                        <ConstraintEditor
                          key={`constraint-${index}`}
                          draft={draft}
                          index={index}
                          onChange={(next) =>
                            setState((prev) => ({
                              ...prev,
                              hardConstraints: prev.hardConstraints.map((item, i) =>
                                i === index ? next : item,
                              ),
                            }))
                          }
                          onRemove={() =>
                            setState((prev) => ({
                              ...prev,
                              hardConstraints: prev.hardConstraints.filter((_, i) => i !== index),
                            }))
                          }
                        />
                      ))}
                    </ul>
                    <button
                      type="button"
                      aria-label="Add constraint"
                      onClick={() =>
                        setState((prev) => ({
                          ...prev,
                          hardConstraints: [
                            ...prev.hardConstraints,
                            { kind: "", kindIsCustom: true, params: [{ key: "", value: "" }] },
                          ],
                        }))
                      }
                      className={addButtonClasses}
                    >
                      Add constraint
                    </button>
                  </>
                )}
              </div>
            </MemberField>

            <MemberField member="beneficiaries" hint="beneficiary_kind + beneficiary_ref.">
              <div className="flex flex-col gap-2">
                <ul className="flex flex-col gap-2">
                  {state.beneficiaries.map((beneficiary, index) => (
                    <li
                      key={`beneficiary-${index}`}
                      className="flex flex-wrap items-center gap-2 rounded-md border border-line bg-raised px-2.5 py-2"
                    >
                      <input
                        aria-label={`beneficiary ${index + 1} beneficiary_kind`}
                        value={beneficiary.beneficiary_kind}
                        onChange={(event) =>
                          setState((prev) => ({
                            ...prev,
                            beneficiaries: prev.beneficiaries.map((item, i) =>
                              i === index
                                ? { ...item, beneficiary_kind: event.target.value }
                                : item,
                            ),
                          }))
                        }
                        placeholder="beneficiary_kind"
                        className={`${monoInputClasses} w-40`}
                      />
                      <input
                        aria-label={`beneficiary ${index + 1} beneficiary_ref`}
                        value={beneficiary.beneficiary_ref}
                        onChange={(event) =>
                          setState((prev) => ({
                            ...prev,
                            beneficiaries: prev.beneficiaries.map((item, i) =>
                              i === index
                                ? { ...item, beneficiary_ref: event.target.value }
                                : item,
                            ),
                          }))
                        }
                        placeholder="beneficiary_ref"
                        className={`${monoInputClasses} min-w-[13rem] flex-1`}
                      />
                      <button
                        type="button"
                        aria-label={`Remove beneficiary ${index + 1}`}
                        onClick={() =>
                          setState((prev) => ({
                            ...prev,
                            beneficiaries: prev.beneficiaries.filter((_, i) => i !== index),
                          }))
                        }
                        className={removeButtonClasses}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  aria-label="Add beneficiary"
                  onClick={() =>
                    setState((prev) => ({
                      ...prev,
                      beneficiaries: [
                        ...prev.beneficiaries,
                        { beneficiary_kind: "", beneficiary_ref: "" },
                      ],
                    }))
                  }
                  className={addButtonClasses}
                >
                  Add beneficiary
                </button>
              </div>
            </MemberField>

            <MemberField
              member="service_properties"
              hint="Opaque typed references (ref_kind “service-property”, fixed)."
            >
              <ValueDraftRows
                labelPrefix="service property"
                drafts={state.serviceProperties}
                onChange={(serviceProperties) =>
                  setState((prev) => ({ ...prev, serviceProperties }))
                }
                addLabel="Add service property"
                addAriaLabel="Add service property"
              />
            </MemberField>

            <MemberField
              member="usage_pricing_terms"
              hint="A single typed reference (ref_kind “usage-pricing-terms”, fixed) — semantics are referenced, never interpreted."
            >
              <input
                aria-label="usage_pricing_terms value"
                value={state.usagePricingValue}
                onChange={(event) =>
                  setState((prev) => ({ ...prev, usagePricingValue: event.target.value }))
                }
                className={`${monoInputClasses} w-80`}
              />
            </MemberField>

            <MemberField
              member="assurance_obligations"
              hint="Typed references with provenance (ref_kind “assurance-obligation”, fixed)."
            >
              <RefDraftRows
                labelPrefix="assurance obligation"
                drafts={state.assuranceObligations}
                onChange={(assuranceObligations) =>
                  setState((prev) => ({ ...prev, assuranceObligations }))
                }
                addLabel="Add assurance obligation"
                addAriaLabel="Add assurance obligation"
              />
            </MemberField>

            <MemberField
              member="execution_scope"
              hint="Typed references (ref_kind “execution-scope”, fixed)."
            >
              <ValueDraftRows
                labelPrefix="execution scope"
                drafts={state.executionScope}
                onChange={(executionScope) => setState((prev) => ({ ...prev, executionScope }))}
                addLabel="Add execution scope reference"
                addAriaLabel="Add execution scope reference"
              />
            </MemberField>

            <MemberField member="recorded_at" hint="RFC 3339 UTC — when the intent is recorded.">
              <input
                aria-label="recorded_at"
                value={state.recordedAt}
                onChange={(event) =>
                  setState((prev) => ({ ...prev, recordedAt: event.target.value }))
                }
                className={`${monoInputClasses} w-60`}
              />
            </MemberField>
          </form>
        ) : (
          <div className="flex flex-col gap-3 rounded-md border border-line bg-surface px-4 py-4">
            <div>
              <label
                htmlFor="canonical-intent-json"
                className="font-mono text-2xs text-ink-faint"
              >
                The canonical intent body (field names are the canonical names)
              </label>
              <textarea
                id="canonical-intent-json"
                aria-label="Canonical intent JSON"
                value={advancedText}
                onChange={(event) => setAdvancedText(event.target.value)}
                spellCheck={false}
                className="mt-1.5 min-h-[28rem] w-full rounded-md border border-line bg-raised p-3 font-mono text-xs leading-relaxed text-ink"
              />
            </div>
            <p
              role="status"
              className={cn(
                "font-mono text-2xs",
                advancedParse.ok ? "text-positive" : "text-danger",
              )}
            >
              {advancedParse.ok
                ? "Valid JSON"
                : `Invalid JSON: ${advancedParse.message}`}
            </p>
          </div>
        )}

        {/* View API request — always visible near the submit button ------ */}
        <section
          aria-labelledby="builder-api-request-heading"
          className="rounded-md border border-line bg-surface"
        >
          <header className="border-b border-line px-4 py-3">
            <h2 id="builder-api-request-heading" className="text-sm font-semibold text-ink">
              View API request
            </h2>
            <p className="mt-0.5 text-xs text-ink-muted">
              Exactly what “Record intent” sends — POST /api/2.0/intents with the
              session headers and the idempotency key generated for this form.
            </p>
          </header>
          <div className="flex flex-col gap-3 px-4 py-3">
            <ApiRequestPanel
              method="POST"
              path="/api/2.0/intents"
              headers={headers}
              body={body}
              description="Request preview — byte-exact preview of the mutation"
            />
            <div data-testid="intent-body-json">
              <CodeBlock
                code={typeof body === "string" ? body : JSON.stringify(body, null, 2)}
                filename="intent.json"
                language="json"
              />
            </div>
            {validation ? (
              <p role="alert" className="text-sm text-danger">
                {validation}
              </p>
            ) : null}
            <p className="text-xs text-ink-faint">
              Client-side checks are convenience only — the backend is the validation
              authority; its verbatim reason codes surface below on rejection.
            </p>
            {submitError ? <ErrorState error={submitError} /> : null}
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void handleSubmit()}
                disabled={pending || !bodyIsObject}
                aria-busy={pending}
                className="inline-flex h-8 items-center rounded-md bg-accent px-3 text-sm text-accent-ink transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
              >
                {pending ? "Recording…" : "Record intent"}
              </button>
              <span className="font-mono text-2xs text-ink-faint">
                POST /api/2.0/intents
              </span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
