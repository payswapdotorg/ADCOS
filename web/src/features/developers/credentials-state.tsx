"use client";

/**
 * CredentialsState — the credentials view (work order deliverable #3).
 *
 * Documents the issuance/reveal rules AS THEY ARE:
 * - the SECRET is never displayed after connection — it lives in the
 *   session store IN MEMORY ONLY and a reload clears it (the console
 *   never persists credentials to any browser storage);
 * - the sandbox demo credential is issued OUT-OF-BAND by the platform
 *   (the runtime prints it at startup);
 * - the console accepts USER-SUPPLIED credentials in the session flow
 *   (the connect dialog validates them against the boundary);
 * - NO rotate or revoke endpoints exist in the accepted API surface —
 *   that is stated honestly instead of dead buttons.
 *
 * The application record's own issuance fields (status, issued_at,
 * valid_until) render verbatim.
 */

import type { Application } from "@/lib/api/types";
import { Status } from "@/components/ui";

export function CredentialsState({ application }: { application: Application }) {
  return (
    <section
      data-testid="credentials-state"
      className="flex flex-col gap-3 rounded-md border border-line bg-surface p-4"
    >
      <div>
        <h2 className="text-sm font-semibold text-ink">Credentials</h2>
        <p className="mt-0.5 text-sm text-ink-muted">
          The issuance state of the connected application&apos;s credential.
        </p>
      </div>

      <dl className="flex flex-col gap-1.5">
        <div className="grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-3">
          <dt className="text-xs text-ink-faint">credential</dt>
          <dd
            data-testid="credential-masked"
            className="font-mono text-xs text-ink-muted"
          >
            •••••••••••• (never displayed after connection)
          </dd>
        </div>
        <div className="grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-3">
          <dt className="text-xs text-ink-faint">status</dt>
          <dd>
            <Status value={application.status} size="sm" />
          </dd>
        </div>
        <div className="grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-3">
          <dt className="text-xs text-ink-faint">issued_at</dt>
          <dd className="font-mono text-xs text-ink">{application.issued_at}</dd>
        </div>
        <div className="grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-3">
          <dt className="text-xs text-ink-faint">valid_until</dt>
          <dd className="font-mono text-xs text-ink">{application.valid_until}</dd>
        </div>
      </dl>

      <div
        data-testid="credential-rules"
        className="flex flex-col gap-2 rounded-md border border-dashed border-line px-3 py-2.5"
      >
        <p className="text-xs leading-relaxed text-ink-muted">
          <span className="font-medium text-ink">Handling.</span> The secret is
          held in memory only for this session — never displayed after
          connection, never persisted to any browser storage, cleared on
          reload.
        </p>
        <p className="text-xs leading-relaxed text-ink-muted">
          <span className="font-medium text-ink">Issuance.</span> The sandbox
          demo credential is issued out-of-band by the platform (the runtime
          prints it at startup); the console accepts user-supplied credentials
          in the session flow and validates them against{" "}
          <span className="font-mono text-2xs">GET /api/2.0/application</span>.
        </p>
        <p className="text-xs leading-relaxed text-ink-muted">
          <span className="font-medium text-ink">Rotate / revoke.</span> No
          credential rotate or revoke endpoints exist in the accepted API
          surface — there is no supported action to offer here, so none is
          shown.
        </p>
      </div>
    </section>
  );
}
