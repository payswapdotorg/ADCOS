"use client";

/**
 * MutationForm — the ONE mutation pattern every contracts surface composes
 * (terminate / grant / renew / revoke / accept offers / activate).
 *
 * Non-negotiables baked in:
 * - the idempotency key is generated ONCE per form instance
 *   (crypto.randomUUID) and passed to the client via MutationOptions, so
 *   the preview panel and the request actually sent agree byte-exactly;
 * - the ApiRequestPanel preview is visible BEFORE submit (method, path,
 *   the non-secret auth headers, the live body) and the request that WAS
 *   sent (body captured at submit time) plus the outcome (HTTP status,
 *   request_id, idempotency replayed marker, the new backend state) is
 *   shown after execution;
 * - failures surface through ErrorState ONLY — the backend's verbatim
 *   reason code is never paraphrased.
 *
 * The credential header (X-ADCOS-Credential) is deliberately NOT rendered:
 * secrets obey the backend's issuance/reveal semantics and are never put
 * on display; the three reproducible headers above are shown verbatim.
 */

import { useState, type ReactNode } from "react";
import type { AdcosEnvelope } from "@/lib/api/types";
import { ApiRequestPanel, ErrorState, Status } from "@/components/ui";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

/** The current instant, RFC 3339 UTC with the millisecond part trimmed. */
export function nowRfc3339(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

export interface MutationFormProps<T> {
  /** HTTP method — every developer-API mutation is POST. */
  method?: string;
  /** The route path, verbatim (e.g. /api/2.0/contracts/{id}/termination). */
  path: string;
  /** The live request body (rendered in the preview, captured on submit). */
  body: unknown;
  /** The explicit confirm button label. */
  confirmLabel: string;
  /** Danger styling for destructive confirms (terminate / revoke). */
  danger?: boolean;
  /** Block submit (client-side sanity only — the backend stays the authority). */
  disabled?: boolean;
  /** Shown next to a disabled confirm. */
  disabledHint?: string;
  /** Performs the mutation through the session's typed client. */
  submit: (idempotencyKey: string) => Promise<AdcosEnvelope<T>>;
  /** Called once on success (refresh reads, record activity). */
  onDone?: (envelope: AdcosEnvelope<T>) => void;
  /** Extra outcome material (e.g. the new state through Status). */
  renderOutcome?: (envelope: AdcosEnvelope<T>) => ReactNode;
}

export function MutationForm<T>({
  method = "POST",
  path,
  body,
  confirmLabel,
  danger = false,
  disabled = false,
  disabledHint,
  submit,
  onDone,
  renderOutcome,
}: MutationFormProps<T>) {
  const { application } = useSession();
  // generated ONCE per form instance — the preview and the sent request
  // therefore carry the same X-ADCOS-Idempotency-Key
  const [idempotencyKey] = useState(() => crypto.randomUUID());
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState<{ body: unknown; envelope: AdcosEnvelope<T> } | null>(
    null,
  );
  const [error, setError] = useState<unknown>(null);

  const headers = [
    { name: "X-ADCOS-Application", value: application?.application_id ?? "" },
    { name: "X-ADCOS-API-Version", value: "2.0" },
    { name: "X-ADCOS-Idempotency-Key", value: idempotencyKey },
  ];

  async function handleSubmit() {
    if (pending || disabled) return;
    setPending(true);
    setError(null);
    try {
      const envelope = await submit(idempotencyKey);
      setSent({ body, envelope });
      onDone?.(envelope);
    } catch (caught) {
      setError(caught);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-3" data-testid="mutation-form">
      <ApiRequestPanel
        method={method}
        path={path}
        headers={headers}
        body={body}
        description={`Request preview — exactly what “${confirmLabel}” sends`}
      />
      {error ? <ErrorState error={error} compact /> : null}
      {sent ? (
        <div
          data-testid="mutation-outcome"
          className="flex flex-col gap-3 rounded-md border border-line bg-raised px-3 py-3"
        >
          <ApiRequestPanel
            method={method}
            path={path}
            headers={headers}
            body={sent.body}
            description="Request sent — exactly what was sent (the same idempotency key replays the same response)"
          />
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span className="text-sm font-medium text-ink">Outcome</span>
            <span className="font-mono text-2xs text-ink-muted">HTTP 200</span>
            <span className="font-mono text-2xs text-ink-muted">
              request_id {sent.envelope.request_id}
            </span>
            <span className="font-mono text-2xs text-ink-muted">
              idempotency_replayed {String(sent.envelope.idempotency?.replayed ?? false)}
            </span>
          </div>
          {renderOutcome ? renderOutcome(sent.envelope) : null}
          <p className="text-2xs text-ink-faint">reads refreshed</p>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={pending || disabled}
            aria-busy={pending}
            className={cn(
              "inline-flex h-8 items-center rounded-md px-3 text-sm transition-colors",
              danger
                ? "border border-danger text-danger hover:bg-danger/10"
                : "border border-line-strong bg-raised text-ink hover:bg-surface",
              (pending || disabled) && "cursor-not-allowed opacity-50",
            )}
          >
            {pending ? "Sending…" : confirmLabel}
          </button>
          {disabled && disabledHint ? (
            <span className="text-xs text-ink-faint">{disabledHint}</span>
          ) : null}
        </div>
      )}
    </div>
  );
}

/** The standard mutation outcome row: the backend state through Status. */
export function StateOutcome({ state }: { state: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-2xs text-ink-faint">state</span>
      <Status value={state} />
    </div>
  );
}
