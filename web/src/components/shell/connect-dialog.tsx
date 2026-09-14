"use client";

/**
 * The connect dialog — the ONLY place credentials are entered.
 *
 * Validates the application id + credential against the real boundary
 * (GET /api/2.0/application) through the session store, which keeps the
 * material IN MEMORY ONLY (never persisted — a reload clears it by
 * design). On failure the backend reason is shown VERBATIM via the
 * ErrorState primitive (e.g. "authentication-invalid"), never rewritten.
 */

import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useState, type FormEvent } from "react";
import { ErrorState } from "@/components/ui";
import { useSession } from "@/lib/session";

export interface ConnectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ConnectDialog({ open, onOpenChange }: ConnectDialogProps) {
  const { status, error, connect } = useSession();
  const connecting = status === "connecting";
  const [applicationId, setApplicationId] = useState("");
  const [credential, setCredential] = useState("");
  const [showCredential, setShowCredential] = useState(false);

  // every open starts from empty fields (credentials are never pre-filled)
  useEffect(() => {
    if (open) {
      setApplicationId("");
      setCredential("");
      setShowCredential(false);
    }
  }, [open]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (connecting) return;
    const id = applicationId.trim();
    const secret = credential;
    if (id.length === 0 || secret.length === 0) return;
    const ok = await connect(id, secret);
    if (ok) onOpenChange(false);
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-canvas/70 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-md border border-line bg-overlay p-5 shadow-[var(--shadow-panel)]">
          <Dialog.Title className="text-lg font-semibold">Connect application</Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-ink-muted">
            Validate an application credential against GET /api/2.0/application.
          </Dialog.Description>

          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="connect-application-id" className="block text-xs text-ink-muted">
                Application ID
              </label>
              <input
                id="connect-application-id"
                name="application-id"
                autoComplete="off"
                spellCheck={false}
                required
                value={applicationId}
                onChange={(event) => setApplicationId(event.target.value)}
                placeholder="sha256:…"
                className="w-full rounded border border-line bg-raised px-2.5 py-1.5 font-mono text-sm text-ink placeholder:text-ink-faint"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="connect-credential" className="block text-xs text-ink-muted">
                Credential
              </label>
              <div className="relative">
                <input
                  id="connect-credential"
                  name="credential"
                  type={showCredential ? "text" : "password"}
                  autoComplete="off"
                  spellCheck={false}
                  required
                  value={credential}
                  onChange={(event) => setCredential(event.target.value)}
                  placeholder="dasec_…"
                  className="w-full rounded border border-line bg-raised px-2.5 py-1.5 pr-14 font-mono text-sm text-ink placeholder:text-ink-faint"
                />
                <button
                  type="button"
                  aria-pressed={showCredential}
                  onClick={() => setShowCredential((shown) => !shown)}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded px-1.5 py-0.5 text-2xs text-ink-muted hover:text-ink"
                >
                  {showCredential ? "Hide" : "Show"}
                </button>
              </div>
              <p className="text-2xs text-ink-faint">
                Issued by the platform. Stored in memory only — never persisted.
              </p>
            </div>

            {error ? <ErrorState error={error} compact /> : null}

            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="rounded border border-line px-3 py-1.5 text-sm text-ink-muted hover:text-ink"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={connecting}
                className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
              >
                {connecting ? "Validating…" : "Connect"}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
