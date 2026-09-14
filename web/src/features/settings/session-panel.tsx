"use client";

/**
 * SessionPanel — the connected application summary + Disconnect, and the
 * console's credential policy (Worker 3, Part C).
 *
 * Honesty rules:
 * - the summary is the application profile the backend returned at
 *   connect (GET /api/2.0/application) — including its evidence_class,
 *   rendered VERBATIM through the badge;
 * - the credential VALUE is never displayed after connect and never
 *   persisted anywhere: memory only, cleared on reload by design;
 * - capabilities render as the backend's own grant strings, verbatim.
 */

import { useState } from "react";
import { ConnectivityIcon, EvidenceBadge, Status } from "@/components/ui";
import { ConnectDialog } from "@/components/shell/connect-dialog";
import { useSession } from "@/lib/session";

/** Stable test ids for the settings suite. */
export const SESSION_PANEL_TEST_IDS = {
  root: "settings-session",
  policy: "settings-credential-policy",
} as const;

export function SessionPanel() {
  const { status, application, disconnect } = useSession();
  const [connectOpen, setConnectOpen] = useState(false);

  const connected = status === "connected";

  return (
    <div
      className="flex flex-col gap-4"
      data-testid={SESSION_PANEL_TEST_IDS.root}
    >
      <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1.5 text-sm">
        <dt className="text-ink-faint">Status</dt>
        <dd className="font-mono text-xs text-ink">{status}</dd>
        {connected && application ? (
          <>
            <dt className="text-ink-faint">Application</dt>
            <dd className="break-all font-mono text-xs text-ink">
              {application.application_name}
            </dd>
            <dt className="text-ink-faint">Application ID</dt>
            <dd className="break-all font-mono text-2xs text-ink-muted">
              {application.application_id}
            </dd>
            <dt className="text-ink-faint">Developer</dt>
            <dd className="break-all font-mono text-2xs text-ink-muted">
              {application.developer_id}
            </dd>
            <dt className="text-ink-faint">State</dt>
            <dd>
              <Status value={application.status} />
            </dd>
            <dt className="text-ink-faint">Environment</dt>
            <dd className="font-mono text-xs text-ink">{application.environment}</dd>
            <dt className="text-ink-faint">Evidence class</dt>
            <dd className="flex items-center gap-2">
              <EvidenceBadge evidenceClass={application.evidence_class} />
              <span className="font-mono text-2xs text-ink-faint">
                verbatim
              </span>
            </dd>
            <dt className="text-ink-faint">Issued</dt>
            <dd className="font-mono text-xs text-ink-muted">
              {application.issued_at}
            </dd>
            <dt className="text-ink-faint">Valid until</dt>
            <dd className="font-mono text-xs text-ink-muted">
              {application.valid_until}
            </dd>
            <dt className="text-ink-faint">Capabilities</dt>
            <dd>
              <ul className="flex max-w-xl flex-wrap gap-1.5">
                {application.capabilities.map((capability) => (
                  <li
                    key={capability}
                    className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted"
                    title={capability}
                  >
                    {capability}
                  </li>
                ))}
              </ul>
            </dd>
          </>
        ) : (
          <dt className="sr-only">Disconnected</dt>
        )}
      </dl>

      <div>
        {connected ? (
          <button
            type="button"
            onClick={disconnect}
            className="rounded border border-line px-3 py-1.5 text-sm text-danger transition-colors hover:bg-danger/10"
          >
            Disconnect
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setConnectOpen(true)}
            className="flex items-center gap-2 rounded border border-line px-3 py-1.5 text-sm text-ink-muted transition-colors hover:text-ink"
          >
            <ConnectivityIcon className="h-3.5 w-3.5" />
            Connect application…
          </button>
        )}
        <ConnectDialog open={connectOpen} onOpenChange={setConnectOpen} />
      </div>

      {/* the credential policy ------------------------------------------ */}
      <p
        data-testid={SESSION_PANEL_TEST_IDS.policy}
        className="text-xs leading-relaxed text-ink-faint"
      >
        Credential policy: the application id and credential are held in
        memory only — never written to localStorage, sessionStorage or
        cookies — and are cleared on reload by design. The credential value
        is never displayed after connect and never echoed in full anywhere
        (reproductions mask it). Secrets obey the backend&apos;s
        issuance/reveal semantics; the console only carries them for the
        lifetime of the tab.
      </p>
    </div>
  );
}
