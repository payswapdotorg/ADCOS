"use client";

/**
 * ErrorWorkbench — the session's captured errors with the full anatomy
 * (what happened / why / affected resource / next action / reproducible
 * API form), at the FROZEN path /settings/errors.
 *
 * The captured-error source is the in-memory request log (READ-ONLY
 * consume: `useRequestLog` + `isFailedRequest`) — display data only,
 * never authority. Entries carry the recorder's enrichment WHENEVER it
 * captured them; an entry recorded before any inspector-capable page
 * mounted simply renders without the extra fields (nothing fabricated).
 *
 * Deep-linking: `workbenchHref(sequence)` produces
 * /settings/errors?request=<sequence> — the workbench preselects and
 * expands that entry; a stale sequence (the log is in-memory, cleared on
 * reload) renders an honest note instead of pretending.
 */

import { useEffect, useState } from "react";
import { isFailedRequest, useRequestLog } from "@/features/requests/request-log";
import { ensureRequestRecorder } from "@/features/requests/recorder";
import { EmptyState } from "@/components/ui";
import { useSearchParams } from "next/navigation";
import { CapturedErrorCard } from "./captured-error-card";

/** Stable test id for the workbench root. */
export const ERROR_WORKBENCH_TEST_IDS = {
  root: "error-workbench",
  empty: "workbench-empty",
  deepLinkNote: "workbench-deep-link-note",
} as const;

export function ErrorWorkbench() {
  const requests = useRequestLog();

  // capture-eligible from here on: requests made while this (or any other
  // recorder-installing) surface is mounted record their completions
  useEffect(() => {
    ensureRequestRecorder();
  }, []);

  const searchParams = useSearchParams();
  const requested = searchParams.get("request");
  const requestedSequence =
    requested !== null && requested.trim() !== "" && Number.isFinite(Number(requested))
      ? Number(requested)
      : null;

  const [selected, setSelected] = useState<number | null>(null);

  // the deep-link preselection (fires whenever ?request= changes)
  useEffect(() => {
    if (requestedSequence !== null) {
      setSelected(requestedSequence);
    }
  }, [requestedSequence]);

  const failed = requests.filter(isFailedRequest);
  const requestedStale =
    requestedSequence !== null &&
    !failed.some((entry) => entry.sequence === requestedSequence);

  return (
    <div
      className="mx-auto w-full max-w-workbench px-gutter py-rhythm"
      data-testid={ERROR_WORKBENCH_TEST_IDS.root}
    >
      <div className="flex flex-col gap-4">
        <header>
          <h1 className="text-xl font-semibold text-ink">Error workbench</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Every captured failure answers: what happened, why, the affected
            resource, the next action, and the reproducible API form. Reason
            codes render VERBATIM — never replaced with a generic message.
          </p>
          <p className="mt-1 text-xs text-ink-faint">
            Captured errors are the failed requests THIS console session made
            through the typed client — in-memory like the session itself, so a
            reload clears them by design. The credential is never echoed in
            full: reproductions mask it.
          </p>
        </header>

        {requestedStale ? (
          <div
            data-testid={ERROR_WORKBENCH_TEST_IDS.deepLinkNote}
            className="rounded-md border border-dashed border-warning/60 bg-warning/5 px-3 py-2"
          >
            <p className="text-sm text-ink-muted">
              The link asked for request #{requestedSequence}, which is not in
              the captured log — the log is in-memory and a reload clears it.
              Every captured error is listed below.
            </p>
          </div>
        ) : null}

        {failed.length === 0 ? (
          <div
            className="rounded-md border border-line bg-surface"
            data-testid={ERROR_WORKBENCH_TEST_IDS.empty}
          >
            <EmptyState
              title="No captured errors"
              description={
                <span>
                  Every request this console session made succeeded. Failed
                  requests appear here with their full anatomy — the reason
                  code verbatim, per-code guidance, a retry when the backend
                  marked the error retryable, and a copyable curl
                  reproduction with the credential masked.
                </span>
              }
            />
          </div>
        ) : (
          <ul className="flex flex-col gap-3">
            {failed.map((entry) => (
              <CapturedErrorCard
                key={entry.sequence}
                entry={entry}
                expanded={
                  selected === null
                    ? entry === failed[0]
                    : entry.sequence === selected
                }
                onToggle={() =>
                  setSelected((current) =>
                    current === entry.sequence ? null : entry.sequence,
                  )
                }
                onPin={() => setSelected(entry.sequence)}
              />
            ))}
          </ul>
        )}

        <p className="text-xs text-ink-faint">
          The captured log holds the last 50 requests (successes and
          failures); only the failures render here. Inspect the full request
          log in Developers → Request inspector.
        </p>
      </div>
    </div>
  );
}
