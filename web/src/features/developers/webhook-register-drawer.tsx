"use client";

/**
 * WebhookRegisterDrawer — the endpoint registration form (work order
 * deliverable #4, register).
 *
 * Vocabulary discipline (hard constraint #4): the event-type choices
 * are EXACTLY the frozen vocabulary, rendered as a checkbox list —
 * there is NO text input for event types anywhere in this form, so a
 * free-text event type is impossible by construction. The backend
 * rejects non-members with `invalid-input` ("event type … is not in
 * the frozen vocabulary") and an empty subscription with
 * `invalid-input` ("a webhook endpoint must subscribe to at least one
 * event type").
 *
 * Mutation discipline: the request is previewed BEFORE submit
 * (ApiRequestPanel), sent through the typed client (which adds the
 * idempotency key automatically), and the outcome renders AFTER —
 * the endpoint record with its key_id on success (no secret material
 * is returned by this API: the signing secret is derived platform-side
 * and never exposed through the boundary), the verbatim reason on
 * failure. Local validation problems are labeled as local — never
 * fabricated as backend reasons.
 */

import { useState } from "react";
import type { AdcosEnvelope, WebhookEndpoint } from "@/lib/api/types";
import { useSession } from "@/lib/session";
import { LinkedErrorState } from "@/features/errors/link";
import {
  ApiRequestPanel,
  CopyButton,
  Drawer,
  JsonViewer,
} from "@/components/ui";
import { WEBHOOK_EVENT_TYPES } from "./webhook-event-types";
import { cn } from "@/lib/utils";

const inputClasses =
  "h-8 w-full rounded-md border border-line bg-raised px-2 font-mono text-sm text-ink";

type Outcome =
  | { kind: "success"; envelope: AdcosEnvelope<WebhookEndpoint> }
  | { kind: "error"; error: unknown }
  | null;

export function WebhookRegisterDrawer({
  canWrite,
  onClose,
  onRegistered,
}: {
  /** Is `webhooks:write` granted? (named verbatim when not) */
  canWrite: boolean;
  onClose: () => void;
  /** Called with the registered record (refreshes the list). */
  onRegistered: (envelope: AdcosEnvelope<WebhookEndpoint>) => void;
}) {
  const { client } = useSession();
  const [url, setUrl] = useState("");
  const [selected, setSelected] = useState<readonly string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [outcome, setOutcome] = useState<Outcome>(null);

  const trimmed = url.trim();
  const urlLooksValid = /^https?:\/\//.test(trimmed);
  const hasSelection = selected.length > 0;
  const succeeded = outcome?.kind === "success";

  // the body exactly as the typed client will send it (canonical
  // vocabulary order — the backend returns event_types sorted)
  const body = {
    url: trimmed,
    event_types: WEBHOOK_EVENT_TYPES.filter((eventType) =>
      selected.includes(eventType),
    ),
  };

  function toggleEventType(eventType: string) {
    setSelected((previous) =>
      previous.includes(eventType)
        ? previous.filter((value) => value !== eventType)
        : [...previous, eventType],
    );
  }

  async function submit(): Promise<void> {
    if (submitting || succeeded) return;
    setSubmitting(true);
    try {
      const envelope = await client.registerWebhookEndpoint(body);
      setOutcome({ kind: "success", envelope });
    } catch (error) {
      setOutcome({ kind: "error", error });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Register webhook endpoint"
      description="POST /api/2.0/webhook-endpoints — an X-ADCOS-Idempotency-Key header is generated automatically"
    >
      <div className="flex flex-col gap-4">
        {succeeded && outcome.kind === "success" ? (
          <RegisteredOutcome
            envelope={outcome.envelope}
            onDone={() => {
              onRegistered(outcome.envelope);
              onClose();
            }}
            onAnother={() => {
              setOutcome(null);
              setUrl("");
              setSelected([]);
            }}
          />
        ) : (
          <>
            <p className="text-sm leading-relaxed text-ink-muted">
              The platform delivers signed events to your endpoint. Event types
              come from the backend&apos;s frozen vocabulary — checkboxes only,
              there is no free-text event type. The URL must be an http(s) URL
              and at least one event type is required; the backend rejects
              otherwise with{" "}
              <span className="font-mono text-2xs">invalid-input</span>.
            </p>

            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="webhook-url"
                className="font-mono text-2xs text-ink-faint"
              >
                url
              </label>
              <input
                id="webhook-url"
                name="url"
                autoComplete="off"
                spellCheck={false}
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://example.com/hooks/adcos"
                className={inputClasses}
              />
              {trimmed !== "" && !urlLooksValid ? (
                <p
                  data-testid="webhook-url-local-validation"
                  className="text-xs text-warning"
                >
                  Local check: the backend requires an http(s) URL.
                </p>
              ) : null}
            </div>

            <fieldset
              data-testid="webhook-event-types"
              className="flex flex-col gap-2"
            >
              <legend className="font-mono text-2xs text-ink-faint">
                event_types (frozen vocabulary — {selected.length} of{" "}
                {WEBHOOK_EVENT_TYPES.length} selected)
              </legend>
              <ul className="grid grid-cols-1 gap-1">
                {WEBHOOK_EVENT_TYPES.map((eventType) => {
                  const checked = selected.includes(eventType);
                  return (
                    <li key={eventType}>
                      <label
                        className={cn(
                          "flex cursor-pointer items-center gap-2 rounded-md border px-2 py-1.5 transition-colors",
                          checked
                            ? "border-accent bg-accent/10"
                            : "border-line bg-raised hover:border-line-strong",
                        )}
                      >
                        <input
                          type="checkbox"
                          value={eventType}
                          checked={checked}
                          onChange={() => toggleEventType(eventType)}
                          data-testid="webhook-event-type-option"
                        />
                        <span className="font-mono text-xs text-ink">
                          {eventType}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
              {!hasSelection ? (
                <p className="text-xs text-ink-faint">
                  At least one event type is required (the backend rejects an
                  empty subscription).
                </p>
              ) : null}
            </fieldset>

            <ApiRequestPanel
              variant="full"
              method="POST"
              path="/api/2.0/webhook-endpoints"
              body={body}
              description="The request this form will send — review it before submitting."
            />

            {outcome?.kind === "error" ? (
              <LinkedErrorState
                error={outcome.error}
                onRetry={() => setOutcome(null)}
                request={{
                  method: "POST",
                  path: "/api/2.0/webhook-endpoints",
                  body,
                }}
              />
            ) : null}

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="h-8 rounded-md border border-line bg-raised px-3 text-sm text-ink-muted transition-colors hover:text-ink"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void submit()}
                disabled={
                  submitting ||
                  !urlLooksValid ||
                  !hasSelection ||
                  !canWrite ||
                  trimmed === ""
                }
                data-testid="webhook-register-submit"
                className="h-8 rounded-md bg-accent px-3 text-sm text-accent-ink transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Registering…" : "Register endpoint"}
              </button>
            </div>

            {!canWrite ? (
              <p
                data-testid="webhooks-write-denied"
                className="rounded-md border border-dashed border-danger/60 bg-danger/5 px-3 py-2 text-xs leading-relaxed text-ink-muted"
              >
                This application lacks{" "}
                <span className="font-mono text-danger">webhooks:write</span>{" "}
                (required by the operation registry). The backend would reject
                the registration with{" "}
                <span className="font-mono text-ink">capability-denied</span>{" "}
                naming that capability verbatim.
              </p>
            ) : null}
          </>
        )}
      </div>
    </Drawer>
  );
}

/* ------------------------------------------------------------------ */

function RegisteredOutcome({
  envelope,
  onDone,
  onAnother,
}: {
  envelope: AdcosEnvelope<WebhookEndpoint>;
  onDone: () => void;
  onAnother: () => void;
}) {
  const endpoint = envelope.data;
  return (
    <div data-testid="webhook-registered-outcome" className="flex flex-col gap-4">
      <p className="text-sm text-ink-muted">
        Registered — the endpoint record as the backend returned it:
      </p>
      <dl className="flex flex-col gap-1.5 rounded-md border border-line bg-raised px-3 py-2.5">
        <div className="grid grid-cols-[minmax(6rem,auto)_1fr] gap-x-3">
          <dt className="text-xs text-ink-faint">id</dt>
          <dd className="flex min-w-0 items-center gap-1">
            <span
              className="break-all font-mono text-xs text-ink"
              title={endpoint.id}
            >
              {endpoint.id}
            </span>
            <CopyButton
              value={endpoint.id}
              ariaLabel="Copy endpoint id"
              label="Copy"
            />
          </dd>
        </div>
        <div className="grid grid-cols-[minmax(6rem,auto)_1fr] gap-x-3">
          <dt className="text-xs text-ink-faint">key_id</dt>
          <dd className="break-all font-mono text-xs text-ink">
            {endpoint.key_id}
          </dd>
        </div>
        <div className="grid grid-cols-[minmax(6rem,auto)_1fr] gap-x-3">
          <dt className="text-xs text-ink-faint">created_at</dt>
          <dd className="font-mono text-xs text-ink">{endpoint.created_at}</dd>
        </div>
        <div className="grid grid-cols-[minmax(6rem,auto)_1fr] gap-x-3">
          <dt className="text-xs text-ink-faint">url</dt>
          <dd className="break-all font-mono text-xs text-ink">{endpoint.url}</dd>
        </div>
        <div className="grid grid-cols-[minmax(6rem,auto)_1fr] gap-x-3">
          <dt className="text-xs text-ink-faint">event_types</dt>
          <dd className="font-mono text-xs text-ink">
            {endpoint.event_types.join(", ")}
          </dd>
        </div>
      </dl>
      <p className="text-xs leading-relaxed text-ink-muted">
        No signing secret is returned by this API — the secret is derived
        platform-side and never exposed through the boundary; only the{" "}
        <span className="font-mono text-2xs">key_id</span> above identifies the
        signing key. Deliveries sign with that key and are verifiable with the
        platform&apos;s documented construction.
      </p>
      <JsonViewer value={endpoint} name="data" defaultExpandedDepth={1} />
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onAnother}
          className="h-8 rounded-md border border-line bg-raised px-3 text-sm text-ink-muted transition-colors hover:text-ink"
        >
          Register another
        </button>
        <button
          type="button"
          onClick={onDone}
          data-testid="webhook-register-done"
          className="h-8 rounded-md bg-accent px-3 text-sm text-accent-ink transition-colors hover:bg-accent-strong"
        >
          Done
        </button>
      </div>
    </div>
  );
}
