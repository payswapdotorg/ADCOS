"use client";

/**
 * OperationDetail — the request builder for ONE registry operation.
 *
 * Renders exactly what an execution will carry: method + rendered path,
 * the boundary headers (the session's ACTUAL application id when
 * connected; the credential ALWAYS masked — `maskedRequestHeaders` is
 * the single source for both the table and the curl), path parameters
 * for templated routes, and the JSON body editor for mutations (seeded
 * from the registry's own `example`, locally validated — a local
 * problem is reported as such, NEVER fabricated as a backend reason).
 *
 * Disciplines enforced here:
 * - destructive operations (DESTRUCTIVE_OPERATIONS) require an explicit
 *   confirmation step before `onExecute` can fire;
 * - GET list reads carry the browser discipline notice (pagination and
 *   filters ride the GET request's JSON body — unsendable from any
 *   browser; the executor performs the bodyless default-page read and
 *   the canonical API form is reproduced for out-of-browser use);
 * - authenticated developer operations are gated on a connected session
 *   (platform surfaces stay executable — they need no session);
 * - a missing capability is surfaced honestly but never pre-denied: the
 *   backend owns authorization and answers `capability-denied` itself.
 */

import { useMemo } from "react";
import type { CoverageRecord } from "@/lib/api/coverage";
import { capabilityGranted } from "@/features/developers/capabilities";
import {
  DESTRUCTIVE_OPERATIONS,
  maskedRequestHeaders,
  pathParameterNames,
  renderPath,
} from "./executor";
import { ApiRequestPanel } from "@/components/ui";

/** The developer-API list reads (registry ids, verbatim). */
const LIST_OPERATIONS = new Set([
  "intents_list",
  "contracts_list",
  "leases_list",
  "endpoints_list",
  "deliveries_list",
]);

/** The canonical GET-body form per list operation (reproducible outside the browser). */
const LIST_BODY_EXAMPLES: Record<string, Record<string, unknown>> = {
  intents_list: { limit: 20, cursor: "<next_cursor>" },
  contracts_list: { limit: 20, cursor: "<next_cursor>", filters: { state: "<state>" } },
  leases_list: { limit: 20, cursor: "<next_cursor>", filters: { state: "<state>" } },
  endpoints_list: { limit: 20, cursor: "<next_cursor>" },
  deliveries_list: { limit: 20, cursor: "<next_cursor>" },
};

function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `adcos-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function freshIdempotencyKey(): string {
  return newIdempotencyKey();
}

function MethodChip({ method }: { method: string }) {
  const read = method === "GET";
  return (
    <span
      className={
        read
          ? "inline-flex shrink-0 items-center rounded border border-line-strong px-1.5 py-px font-mono text-xs uppercase tracking-wide text-ink-muted"
          : "inline-flex shrink-0 items-center rounded border border-accent bg-accent px-1.5 py-px font-mono text-xs uppercase tracking-wide text-accent-ink"
      }
    >
      {method}
    </span>
  );
}

export function OperationDetail({
  record,
  connected,
  applicationId,
  capabilities,
  pathParams,
  onPathParamChange,
  bodyText,
  onBodyTextChange,
  bodyEditable,
  idempotencyKey,
  onIdempotencyKeyChange,
  confirming,
  onRequestExecute,
  onConfirmExecute,
  onCancelConfirm,
  running,
  invalidMessage,
}: {
  record: CoverageRecord;
  connected: boolean;
  applicationId: string | null;
  capabilities: string[] | null;
  pathParams: Record<string, string>;
  onPathParamChange: (name: string, value: string) => void;
  bodyText: string;
  onBodyTextChange: (value: string) => void;
  bodyEditable: boolean;
  idempotencyKey: string;
  onIdempotencyKeyChange: (value: string) => void;
  confirming: boolean;
  /** Arms (destructive) or fires (everything else) the execution. */
  onRequestExecute: () => void;
  /** Fires an armed destructive execution after explicit confirmation. */
  onConfirmExecute: () => void;
  onCancelConfirm: () => void;
  running: boolean;
  invalidMessage: string | null;
}) {
  const destructive = DESTRUCTIVE_OPERATIONS.has(record.operation);
  const listRead = LIST_OPERATIONS.has(record.operation);
  const capability = capabilityGranted(record.requiredCapability, capabilities);
  const authenticated = !record.platform;

  const paramNames = pathParameterNames(record.path);
  const renderedPath = renderPath(record.path, pathParams);

  const headers = useMemo(
    () =>
      maskedRequestHeaders({
        platform: record.platform,
        mutation: record.mutation,
        applicationId,
        idempotencyKey: record.mutation ? idempotencyKey.trim() || null : null,
      }),
    [record.platform, record.mutation, applicationId, idempotencyKey],
  );

  // local JSON validation — reported as LOCAL, never as a backend reason
  const bodyError = useMemo(() => {
    if (!bodyEditable || bodyText.trim().length === 0) return null;
    try {
      JSON.parse(bodyText);
      return null;
    } catch (error) {
      return error instanceof Error ? error.message : String(error);
    }
  }, [bodyEditable, bodyText]);

  const executeBlocked =
    running ||
    bodyError !== null ||
    (authenticated && !connected);

  return (
    <section
      aria-label={`Operation ${record.operation}`}
      className="flex flex-col gap-4 rounded-md border border-line bg-surface p-4"
    >
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <MethodChip method={record.method} />
          <span className="min-w-0 break-all font-mono text-sm text-ink">
            {renderedPath}
          </span>
          {record.mutation ? (
            <span className="rounded border border-accent/60 px-1.5 py-px font-mono text-2xs text-accent">
              mutation · idempotency key required
            </span>
          ) : null}
          {destructive ? (
            <span className="rounded border border-danger/60 px-1.5 py-px font-mono text-2xs text-danger">
              destructive · confirmation required
            </span>
          ) : null}
        </div>
        <p className="text-sm text-ink-muted">{record.description}</p>
        <p className="font-mono text-2xs text-ink-faint">
          operation: {record.operation} · surfaced at {record.uiLocation}
          {record.requiredCapability ? ` · capability: ${record.requiredCapability}` : ""}
        </p>
      </div>

      {authenticated && !connected ? (
        <div className="rounded-md border border-dashed border-warning/60 bg-warning/5 px-3 py-2">
          <p className="text-sm text-ink">
            Connect an application to execute authenticated developer-API operations.
          </p>
          <p className="mt-1 text-xs text-ink-muted">
            This operation carries X-ADCOS-Application / X-ADCOS-Credential /
            X-ADCOS-API-Version headers the session must supply (platform surfaces
            below need none).
          </p>
        </div>
      ) : null}

      {authenticated && connected && capability === false ? (
        <div className="rounded-md border border-dashed border-warning/60 bg-warning/5 px-3 py-2">
          <p className="text-sm text-ink">
            The connected application lacks <span className="font-mono">{record.requiredCapability}</span>.
          </p>
          <p className="mt-1 text-xs text-ink-muted">
            Execution stays available — the backend authorizes every request itself
            and answers <span className="font-mono">capability-denied</span> verbatim
            when the grant is missing.
          </p>
        </div>
      ) : null}

      <div className="flex flex-col gap-1.5">
        <p className="text-2xs uppercase tracking-wide text-ink-faint">Request headers</p>
        <dl className="flex flex-col gap-1 rounded-md border border-line bg-raised px-2.5 py-2">
          {headers.length > 0 ? (
            headers.map((header) => (
              <div
                key={header.name}
                className="grid grid-cols-[minmax(11rem,auto)_1fr] gap-x-3"
              >
                <dt className="truncate font-mono text-2xs text-ink-faint" title={header.name}>
                  {header.name}
                </dt>
                <dd className="break-all font-mono text-xs text-ink">{header.value}</dd>
              </div>
            ))
          ) : (
            <div className="text-xs text-ink-muted">
              No boundary headers — this platform surface is unauthenticated.
            </div>
          )}
          {bodyEditable && bodyText.trim().length > 0 ? (
            <div className="grid grid-cols-[minmax(11rem,auto)_1fr] gap-x-3">
              <dt className="font-mono text-2xs text-ink-faint">Content-Type</dt>
              <dd className="font-mono text-xs text-ink">application/json</dd>
            </div>
          ) : null}
        </dl>
        <p className="text-2xs text-ink-faint">
          The credential is never displayed or copied in full — reproductions carry
          the masked placeholder.
        </p>
      </div>

      {paramNames.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          <p className="text-2xs uppercase tracking-wide text-ink-faint">Path parameters</p>
          <div className="flex flex-col gap-2">
            {paramNames.map((name) => (
              <label key={name} className="flex flex-col gap-1">
                <span className="font-mono text-2xs text-ink-muted">{`{${name}}`}</span>
                <input
                  type="text"
                  value={pathParams[name] ?? ""}
                  onChange={(event) => onPathParamChange(name, event.target.value)}
                  placeholder={`backend-minted ${name.replace(/_/g, " ")}`}
                  aria-label={`Path parameter ${name}`}
                  className="h-8 rounded-md border border-line bg-raised px-2.5 font-mono text-xs text-ink placeholder:text-ink-faint"
                />
              </label>
            ))}
          </div>
        </div>
      ) : null}

      {bodyEditable ? (
        <div className="flex flex-col gap-1.5">
          <p className="text-2xs uppercase tracking-wide text-ink-faint">
            Request body (JSON — editable)
          </p>
          <textarea
            value={bodyText}
            onChange={(event) => onBodyTextChange(event.target.value)}
            aria-label="Request body JSON"
            rows={10}
            spellCheck={false}
            className="w-full rounded-md border border-line bg-raised p-2.5 font-mono text-xs leading-relaxed text-ink"
          />
          {bodyError ? (
            <p className="text-xs text-danger" data-testid="body-validation-error">
              Local validation — the body is not valid JSON: {bodyError}
            </p>
          ) : null}
          {record.operation === "demo_contract_fulfillment" ? (
            <p className="text-2xs text-ink-faint">
              With an <span className="font-mono">instant</span> the request executes
              as POST /demo/contract-fulfillment; an empty body executes the default
              GET form.
            </p>
          ) : null}
        </div>
      ) : null}

      {record.mutation ? (
        <div className="flex flex-col gap-1.5">
          <p className="text-2xs uppercase tracking-wide text-ink-faint">
            X-ADCOS-Idempotency-Key
          </p>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={idempotencyKey}
              onChange={(event) => onIdempotencyKeyChange(event.target.value)}
              aria-label="Idempotency key"
              placeholder="auto-generated by the client when empty"
              className="h-8 min-w-0 flex-1 rounded-md border border-line bg-raised px-2.5 font-mono text-xs text-ink placeholder:text-ink-faint"
            />
            <button
              type="button"
              onClick={() => onIdempotencyKeyChange(newIdempotencyKey())}
              className="inline-flex h-8 shrink-0 items-center rounded-md border border-line-strong bg-raised px-2.5 text-xs text-ink transition-colors hover:bg-surface"
            >
              New key
            </button>
          </div>
          <p className="text-2xs text-ink-faint">
            Pinned keys make the curl reproduction exact; replaying the same key with
            the same body replays the same response byte-identically.
          </p>
        </div>
      ) : null}

      {listRead ? (
        <div className="flex flex-col gap-2 rounded-md border border-dashed border-warning/60 bg-warning/5 px-3 py-2" data-testid="list-body-discipline-notice">
          <p className="text-sm text-ink-muted">
            Pagination and filters ride this list read&apos;s GET request JSON body —
            a form browsers cannot send (fetch forbids GET bodies). Executing here
            performs the bodyless default-page read; page through the API directly:
          </p>
          <ApiRequestPanel
            variant="compact"
            method="GET"
            path={record.path}
            body={LIST_BODY_EXAMPLES[record.operation] ?? { limit: 20, cursor: "<next_cursor>" }}
          />
        </div>
      ) : null}

      {invalidMessage ? (
        <div
          role="alert"
          className="rounded-md border border-warning/60 bg-warning/5 px-3 py-2"
          data-testid="explorer-invalid-message"
        >
          <p className="text-sm text-ink">Local validation — the request was not sent.</p>
          <p className="mt-1 text-xs text-ink-muted">{invalidMessage}</p>
        </div>
      ) : null}

      <div className="flex flex-col gap-2">
        {destructive && !confirming ? (
          <button
            type="button"
            onClick={onRequestExecute}
            disabled={executeBlocked}
            data-testid="arm-destructive-execute"
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-danger bg-raised px-4 text-sm font-medium text-danger transition-colors hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? "Executing…" : "Execute (destructive)…"}
          </button>
        ) : null}

        {destructive && confirming ? (
          <div
            className="flex flex-col gap-2 rounded-md border border-danger/60 bg-danger/5 px-3 py-3"
            data-testid="destructive-confirmation"
          >
            <p className="text-sm text-ink">
              This operation is destructive and terminal. Confirm to execute the
              REAL request:
            </p>
            <p className="break-all font-mono text-xs text-ink-muted">
              {`${record.method} ${renderedPath}`}
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onConfirmExecute}
                disabled={running}
                data-testid="confirm-destructive-execute"
                className="inline-flex h-8 items-center rounded-md bg-danger px-4 text-sm font-medium text-white transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {running ? "Executing…" : "Confirm and execute"}
              </button>
              <button
                type="button"
                onClick={onCancelConfirm}
                data-testid="cancel-destructive-execute"
                className="inline-flex h-8 items-center rounded-md border border-line-strong bg-raised px-4 text-sm text-ink transition-colors hover:bg-surface"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : null}

        {!destructive ? (
          <button
            type="button"
            onClick={onRequestExecute}
            disabled={executeBlocked}
            data-testid="execute-operation"
            className="inline-flex h-9 items-center justify-center rounded-md bg-accent px-4 text-sm font-medium text-accent-ink transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? "Executing…" : `Execute ${record.method} ${renderedPath}`}
          </button>
        ) : null}
      </div>
    </section>
  );
}
