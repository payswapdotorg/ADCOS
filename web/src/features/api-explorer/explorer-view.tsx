"use client";

/**
 * ApiExplorerView — the /developers/explorer surface.
 *
 * The registry-driven API Explorer: the operation browser (ONLY coverage
 * operations render as callable), the request builder for the selected
 * operation (headers with the session's ACTUAL application id, the
 * credential ALWAYS masked, path parameters, the editable JSON body
 * seeded from the registry's own example), the REAL execution through
 * `executeOperation` (destructive operations gated behind an explicit
 * confirmation), the response pane (status, recorder-captured response
 * headers, the envelope surface, reason codes VERBATIM on errors, the
 * copyable curl with the masked credential), and the replayable
 * execution history for this console session.
 *
 * Deep-link contract (used by the search providers): 
 * `/developers/explorer?operation=<operation>` preselects an operation,
 * and any additional query parameter matching one of its path parameter
 * names prefills it — e.g. `?operation=endpoint_get&endpoint_id=<id>`.
 * An unknown operation id renders the honest "not a supported
 * operation" notice — never a guess.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { coverageByOperation, type CoverageRecord } from "@/lib/api/coverage";
import { useSession } from "@/lib/session";
import { ensureRequestRecorder } from "@/features/requests/recorder";
import { ConsoleSearchProviders } from "@/features/search/providers";
import { EmptyState } from "@/components/ui";
import {
  DESTRUCTIVE_OPERATIONS,
  executeOperation,
  pathParameterNames,
} from "./executor";
import { OperationBrowser } from "./operation-browser";
import { OperationDetail, freshIdempotencyKey } from "./operation-detail";
import { ResponsePane } from "./response-pane";
import {
  appendExplorerExecution,
  useExplorerExecutions,
  type ExplorerExecution,
} from "./explorer-history";
import { correlateLoggedRequest } from "./correlate";

/** The inputs of one (possibly armed) execution — replay uses these too. */
interface PendingExecution {
  operation: string;
  pathParams: Record<string, string>;
  bodyText: string;
  idempotencyKey: string;
}

export function ApiExplorerView() {
  const { status, application, client } = useSession();
  const connected = status === "connected";
  const applicationId = application?.application_id ?? null;
  const capabilities = application?.capabilities ?? null;

  // the recorder enriches every execution with the response headers the
  // response pane renders (installed once, globally, idempotent)
  useEffect(() => {
    ensureRequestRecorder();
  }, []);

  const searchParams = useSearchParams();
  const operationParam = searchParams?.get("operation") ?? "";

  const [selected, setSelected] = useState<string | null>(null);
  const [unknownOperation, setUnknownOperation] = useState<string | null>(null);
  const [pathParams, setPathParams] = useState<Record<string, string>>({});
  const [bodyText, setBodyText] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [browserQuery, setBrowserQuery] = useState("");
  const [pending, setPending] = useState<PendingExecution | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [running, setRunning] = useState(false);
  const [invalidMessage, setInvalidMessage] = useState<string | null>(null);
  const [focusedSequence, setFocusedSequence] = useState<number | null>(null);

  const executions = useExplorerExecutions();
  const selectedRecord: CoverageRecord | null =
    selected !== null ? (coverageByOperation(selected) ?? null) : null;

  const selectOperation = useCallback(
    (record: CoverageRecord, prefilled?: Record<string, string>) => {
      setUnknownOperation(null);
      setSelected(record.operation);
      const initial: Record<string, string> = {};
      for (const name of pathParameterNames(record.path)) {
        initial[name] = prefilled?.[name] ?? "";
      }
      setPathParams(initial);
      setBodyText(
        record.example !== undefined
          ? JSON.stringify(record.example, null, 2)
          : "",
      );
      setIdempotencyKey(record.mutation ? freshIdempotencyKey() : "");
      setConfirming(false);
      setPending(null);
      setInvalidMessage(null);
      setFocusedSequence(null);
    },
    [],
  );

  // the deep link: ?operation=<id> (+ path-parameter prefill via query)
  const lastAppliedParam = useRef<string | null>(null);
  useEffect(() => {
    if (operationParam === "" || lastAppliedParam.current === operationParam) {
      return;
    }
    lastAppliedParam.current = operationParam;
    const record = coverageByOperation(operationParam);
    if (!record) {
      setUnknownOperation(operationParam);
      return;
    }
    const prefilled: Record<string, string> = {};
    for (const name of pathParameterNames(record.path)) {
      const value = searchParams?.get(name);
      if (value) prefilled[name] = value;
    }
    selectOperation(record, prefilled);
  }, [operationParam, searchParams, selectOperation]);

  const runExecution = useCallback(
    async (attempt: PendingExecution) => {
      const record = coverageByOperation(attempt.operation);
      if (!record) return;
      setRunning(true);
      setInvalidMessage(null);
      try {
        const outcome = await executeOperation(client, {
          operation: record.operation,
          pathParams: attempt.pathParams,
          body: attempt.bodyText.trim().length > 0 ? attempt.bodyText : undefined,
          idempotencyKey:
            record.mutation ? attempt.idempotencyKey.trim() || undefined : undefined,
        });
        if (outcome.kind === "invalid") {
          setInvalidMessage(outcome.message);
          return;
        }
        const requestStatus =
          outcome.kind === "success" ? outcome.status : outcome.error.status;
        const correlated = correlateLoggedRequest({
          method: outcome.request.method,
          path: outcome.request.path,
          body: outcome.request.body,
          status: requestStatus,
        });
        appendExplorerExecution({
          coverage: outcome.coverage,
          request: outcome.request,
          pathParams: attempt.pathParams,
          bodyText: attempt.bodyText,
          idempotencyKey:
            record.mutation ? attempt.idempotencyKey.trim() || undefined : undefined,
          outcome,
          responseHeaders: correlated?.responseHeaders,
          durationMs: correlated?.durationMs,
          responseBody: correlated?.responseBody,
        });
        setFocusedSequence(null);
      } finally {
        setRunning(false);
        setConfirming(false);
        setPending(null);
      }
    },
    [client],
  );

  /** Arms destructive executions; fires everything else immediately. */
  const requestExecution = useCallback(
    (attempt: PendingExecution) => {
      if (DESTRUCTIVE_OPERATIONS.has(attempt.operation)) {
        setPending(attempt);
        setConfirming(true);
        return;
      }
      void runExecution(attempt);
    },
    [runExecution],
  );

  const confirmExecution = useCallback(() => {
    // the confirmation step only ever arms destructive executions
    if (!pending) return;
    void runExecution(pending);
  }, [pending, runExecution]);

  function currentAttempt(): PendingExecution {
    return {
      operation: selected ?? "",
      pathParams,
      bodyText,
      idempotencyKey,
    };
  }

  function replay(entry: ExplorerExecution): void {
    const attempt: PendingExecution = {
      operation: entry.coverage.operation,
      pathParams: entry.pathParams,
      bodyText: entry.bodyText,
      idempotencyKey: entry.idempotencyKey ?? "",
    };
    // the form follows the replayed inputs (context, not authority)
    setSelected(entry.coverage.operation);
    setPathParams(entry.pathParams);
    setBodyText(entry.bodyText);
    setIdempotencyKey(entry.idempotencyKey ?? "");
    setUnknownOperation(null);
    setFocusedSequence(null);
    requestExecution(attempt);
  }

  const displayed =
    (focusedSequence === null
      ? executions[0]
      : executions.find((entry) => entry.sequence === focusedSequence)) ??
    executions[0] ??
    null;

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <ConsoleSearchProviders />
      <div className="flex flex-col gap-4">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-ink">API Explorer</h1>
            <p className="mt-1 text-sm text-ink-muted">
              Every operation below comes from the coverage registry — the
              boundary&apos;s own frozen surface. Executions are REAL requests
              through the typed client; the credential is masked in every
              reproduction.
            </p>
          </div>
        </header>

        {unknownOperation ? (
          <div
            data-testid="unsupported-operation-notice"
            className="rounded-md border border-dashed border-warning/60 bg-warning/5 px-3 py-2"
            role="note"
          >
            <p className="text-sm text-ink">
              <span className="font-mono">{unknownOperation}</span> is not a
              supported operation.
            </p>
            <p className="mt-1 text-xs text-ink-muted">
              The coverage registry is the single source of truth — the link
              that opened this page named an operation outside it.
            </p>
          </div>
        ) : null}

        <div className="grid items-start gap-4 lg:grid-cols-[minmax(280px,340px)_minmax(0,1fr)]">
          <OperationBrowser
            query={browserQuery}
            onQueryChange={setBrowserQuery}
            selectedOperation={selected}
            onSelect={(record, prefilled) => selectOperation(record, prefilled)}
          />

          <div className="flex min-w-0 flex-col gap-4">
            {selectedRecord ? (
              <OperationDetail
                record={selectedRecord}
                connected={connected}
                applicationId={applicationId}
                capabilities={capabilities}
                pathParams={pathParams}
                onPathParamChange={(name, value) =>
                  setPathParams((current) => ({ ...current, [name]: value }))
                }
                bodyText={bodyText}
                onBodyTextChange={setBodyText}
                bodyEditable={selectedRecord.example !== undefined}
                idempotencyKey={idempotencyKey}
                onIdempotencyKeyChange={setIdempotencyKey}
                confirming={confirming}
                onRequestExecute={() => requestExecution(currentAttempt())}
                onConfirmExecute={() => confirmExecution()}
                onCancelConfirm={() => {
                  setConfirming(false);
                  setPending(null);
                }}
                running={running}
                invalidMessage={invalidMessage}
              />
            ) : (
              <div className="rounded-md border border-line bg-surface">
                <EmptyState
                  title="Select an operation"
                  description="Pick an operation from the registry browser, or paste a concrete path into the search — the explorer resolves it through the registry, honestly."
                />
              </div>
            )}

            {displayed ? (
              <ResponsePane execution={displayed} applicationId={applicationId} />
            ) : null}

            {executions.length > 0 ? (
              <section
                aria-label="Execution history"
                className="flex flex-col gap-2 rounded-md border border-line bg-surface p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-ink">
                    Execution history
                  </p>
                  <p className="font-mono text-2xs text-ink-faint" data-testid="explorer-history-count">
                    {executions.length} execution{executions.length === 1 ? "" : "s"} this session
                  </p>
                </div>
                <ul className="flex max-h-72 flex-col gap-1 overflow-y-auto">
                  {executions.map((entry) => {
                    const status =
                      entry.outcome.kind === "success"
                        ? entry.outcome.status
                        : entry.outcome.kind === "error"
                          ? entry.outcome.error.status
                          : null;
                    const focused = displayed?.sequence === entry.sequence;
                    return (
                      <li
                        key={entry.sequence}
                        data-testid="explorer-history-row"
                        className={`flex flex-wrap items-center gap-2 rounded-md border px-2.5 py-1.5 ${
                          focused ? "border-accent bg-raised" : "border-line"
                        }`}
                      >
                        <span className="font-mono text-2xs text-ink-faint">
                          {entry.at}
                        </span>
                        <span
                          className={`inline-flex shrink-0 items-center rounded border px-1.5 py-px font-mono text-2xs ${
                            status !== null && status >= 200 && status < 300
                              ? "border-positive/60 text-positive"
                              : "border-danger/60 text-danger"
                          }`}
                        >
                          {status === null ? "invalid" : status}
                        </span>
                        <span className="min-w-0 flex-1 truncate font-mono text-xs text-ink">
                          {`${entry.request.method} ${entry.request.path}`}
                        </span>
                        {typeof entry.durationMs === "number" ? (
                          <span className="font-mono text-2xs text-ink-faint">
                            {`${entry.durationMs} ms`}
                          </span>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => setFocusedSequence(entry.sequence)}
                          className="inline-flex h-7 shrink-0 items-center rounded-md border border-line-strong bg-raised px-2 text-xs text-ink transition-colors hover:bg-surface"
                        >
                          View
                        </button>
                        <button
                          type="button"
                          onClick={() => replay(entry)}
                          disabled={running}
                          className="inline-flex h-7 shrink-0 items-center rounded-md border border-accent/60 px-2 text-xs text-accent transition-colors hover:bg-accent/10 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Replay
                        </button>
                      </li>
                    );
                  })}
                </ul>
                <p className="text-2xs text-ink-faint">
                  Replay re-runs the recorded inputs through the executor —
                  mutations replay with the SAME idempotency key, which the
                  boundary answers byte-identically.
                </p>
              </section>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
