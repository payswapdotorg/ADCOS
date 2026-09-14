"use client";

/**
 * ApplicationIdentityCard — the credential-state view of the CONNECTED
 * application (work order deliverable #1).
 *
 * Two truth sources, labeled honestly:
 * - the session's already-loaded profile (`application` from
 *   useSession — fetched at connect time) paints instantly;
 * - the page's OWN re-fetch through the typed client
 *   (GET /api/2.0/application) takes precedence once it resolves, and
 *   its request is reproduced in the embedded ApiRequestPanel.
 *
 * Every member renders VERBATIM (ids mono, status through Status,
 * evidence_class through EvidenceBadge). When the re-fetch fails the
 * typed error renders with its reason code VERBATIM and the profile
 * stays labeled as the connect-time snapshot — never invented data.
 */

import type { AdcosEnvelope, Application } from "@/lib/api/types";
import type { DevelopersReadState } from "./use-developers-read";
import { LinkedErrorState } from "@/features/errors/link";
import {
  ApiRequestPanel,
  EvidenceBadge,
  ObjectHeader,
  Status,
} from "@/components/ui";

export function ApplicationIdentityCard({
  application,
  read,
}: {
  /** The session's connect-time profile (instant paint). */
  application: Application | null;
  /** The page's own re-fetch of GET /api/2.0/application. */
  read: DevelopersReadState<AdcosEnvelope<Application>>;
}) {
  const envelope = read.data ?? null;
  const fresh = envelope?.data ?? null;
  const record = fresh ?? application;

  if (!record) {
    return (
      <section
        data-testid="application-identity-loading"
        aria-busy="true"
        className="rounded-md border border-line bg-surface p-4"
      >
        <div className="flex flex-col gap-3">
          <div className="h-6 w-72 animate-pulse rounded bg-raised" />
          <div className="h-4 w-52 animate-pulse rounded bg-raised" />
          <div className="h-16 w-full animate-pulse rounded bg-raised" />
        </div>
      </section>
    );
  }

  const stale = fresh === null; // rendering the connect-time snapshot

  return (
    <section
      data-testid="application-identity-card"
      className="flex flex-col gap-4 rounded-md border border-line bg-surface p-4"
    >
      <ObjectHeader
        kind="application"
        title={record.application_name}
        copyValue={record.application_id}
        status={record.status}
        meta={[
          {
            label: "application_id",
            value: (
              <span
                className="break-all font-mono text-xs text-ink"
                title={record.application_id}
              >
                {record.application_id}
              </span>
            ),
          },
          {
            label: "developer_id",
            value: (
              <span className="break-all font-mono text-xs text-ink">
                {record.developer_id}
              </span>
            ),
          },
          {
            label: "environment",
            value: <span className="chip text-ink-muted">{record.environment}</span>,
          },
          {
            label: "evidence_class",
            value: <EvidenceBadge evidenceClass={record.evidence_class} size="sm" />,
          },
          {
            label: "status",
            value: <Status value={record.status} size="sm" />,
          },
          {
            label: "issued_at",
            value: (
              <span className="font-mono text-xs text-ink">{record.issued_at}</span>
            ),
          },
          {
            label: "valid_until",
            value: (
              <span className="font-mono text-xs text-ink">{record.valid_until}</span>
            ),
          },
          {
            label: "API version",
            value: (
              <span className="font-mono text-xs text-ink">
                {envelope?.api_version ?? "—"}
              </span>
            ),
          },
        ]}
      />

      {read.error ? (
        <LinkedErrorState
          error={read.error}
          onRetry={read.refresh}
          request={{ method: "GET", path: "/api/2.0/application" }}
        />
      ) : null}

      <div className="flex flex-col gap-2">
        <p className="text-xs text-ink-faint">
          {stale
            ? "Session profile (loaded at connect time) — the page's re-fetch is in flight. The API version rides every request as X-ADCOS-API-Version: 2.0."
            : `Re-read on this page${
                envelope?.request_id ? ` · request_id: ${envelope.request_id}` : ""
              }`}
        </p>
        <ApiRequestPanel
          variant="full"
          method="GET"
          path="/api/2.0/application"
          description="The read behind this card — sent on every visit with the session headers."
        />
      </div>

      {stale ? (
        <p className="rounded-md border border-dashed border-line px-3 py-2 text-xs text-ink-faint">
          While the re-fetch is in flight this card renders the profile the
          session validated at connect time — never a fabricated one.
        </p>
      ) : null}
    </section>
  );
}
