"use client";

/**
 * HealthPanel — the environment/health section of Settings (Worker 3,
 * Part C): the FULL /readyz document (mode, environment, every backend
 * state + detail, delegated backends) plus /healthz — with the honest
 * semantics stated explicitly:
 *
 * - GET /healthz is LIVENESS: it says the runtime process is up — it
 *   says NOTHING about backends;
 * - GET /readyz is READINESS: it names every backend and its state —
 *   a runtime can be live while individual backends are unavailable.
 *
 * Both reads are unauthenticated platform surfaces through the typed
 * client (they work with no session connected); refresh re-reads truth.
 */

import { useEffect, useState } from "react";
import type { Healthz, Readiness, ReadinessBackend } from "@/lib/api/types";
import { ErrorState, RefreshIcon } from "@/components/ui";
import { isAdcosApiError } from "@/lib/api/errors";
import { ensureRequestRecorder } from "@/features/requests/recorder";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

/** Stable test ids for the settings suite. */
export const HEALTH_PANEL_TEST_IDS = {
  root: "settings-health",
  semantics: "health-semantics",
  readiness: "readyz-document",
  liveness: "healthz-document",
  refresh: "health-refresh",
} as const;

function backendStateClass(state: string): string {
  if (state === "ready") return "text-positive";
  if (state === "unavailable") return "text-danger";
  return "text-warning";
}

function BackendRows({
  backends,
}: {
  backends: Record<string, ReadinessBackend>;
}) {
  const rows = Object.entries(backends);
  if (rows.length === 0) {
    return (
      <p className="text-sm text-ink-faint">
        No backends reported in the readiness document — the runtime itself
        named none (in sandbox mode the composition holds no durable
        backends).
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-1.5">
      {rows.map(([name, backend]) => (
        <li
          key={name}
          data-testid="readyz-backend"
          className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 rounded border border-line bg-raised px-2 py-1.5"
        >
          <span className="min-w-0 break-all font-mono text-xs text-ink">
            {name}
          </span>
          <span
            className={cn(
              "font-mono text-xs",
              backendStateClass(backend.state),
            )}
          >
            {backend.state}
          </span>
          <span className="min-w-0 flex-1 break-all font-mono text-2xs text-ink-faint">
            {backend.detail}
          </span>
        </li>
      ))}
    </ul>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] items-baseline gap-x-3">
      <dt className="font-mono text-2xs text-ink-faint">{label}</dt>
      <dd className="min-w-0 break-all font-mono text-xs text-ink">{value}</dd>
    </div>
  );
}

export function HealthPanel() {
  const { client } = useSession();

  const [tick, setTick] = useState(0);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [readinessError, setReadinessError] = useState<unknown>(null);
  const [readinessLoading, setReadinessLoading] = useState(true);
  const [liveness, setLiveness] = useState<Healthz | null>(null);
  const [livenessError, setLivenessError] = useState<unknown>(null);
  const [livenessLoading, setLivenessLoading] = useState(true);

  useEffect(() => {
    ensureRequestRecorder();
  }, []);

  useEffect(() => {
    let mounted = true;
    setReadinessLoading(true);
    setLivenessLoading(true);
    setReadinessError(null);
    setLivenessError(null);

    client
      .readyz()
      .then((document) => {
        if (mounted) setReadiness(document);
      })
      .catch((error: unknown) => {
        if (mounted) {
          setReadiness(null);
          setReadinessError(error);
        }
      })
      .finally(() => {
        if (mounted) setReadinessLoading(false);
      });

    client
      .healthz()
      .then((document) => {
        if (mounted) setLiveness(document);
      })
      .catch((error: unknown) => {
        if (mounted) {
          setLiveness(null);
          setLivenessError(error);
        }
      })
      .finally(() => {
        if (mounted) setLivenessLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [client, tick]);

  const readinessDegraded = readiness !== null && readiness.ok !== true;
  const degraded503 =
    readinessError !== null &&
    isAdcosApiError(readinessError) &&
    readinessError.status === 503;

  return (
    <div className="flex flex-col gap-4" data-testid={HEALTH_PANEL_TEST_IDS.root}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-ink-faint">
          Unauthenticated platform reads through the typed client — they work
          with no session connected. Refresh re-reads truth.
        </p>
        <button
          type="button"
          data-testid={HEALTH_PANEL_TEST_IDS.refresh}
          onClick={() => setTick((value) => value + 1)}
          disabled={readinessLoading || livenessLoading}
          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface disabled:opacity-50"
        >
          <RefreshIcon size={14} />
          Refresh health
        </button>
      </div>

      {/* the honest semantics ------------------------------------------ */}
      <div
        data-testid={HEALTH_PANEL_TEST_IDS.semantics}
        className="rounded-md border border-line bg-raised px-3 py-2.5"
      >
        <p className="text-sm text-ink-muted">
          <span className="font-medium text-ink">Liveness ≠ readiness.</span>{" "}
          GET /healthz is liveness: it says the runtime process is up — it says{" "}
          <span className="font-medium text-ink">nothing about backends</span>{" "}
          (its document carries only ok and service). GET /readyz is
          readiness: it names{" "}
          <span className="font-medium text-ink">every backend and its state</span>{" "}
          — a runtime can be live (healthz ok) while individual backends are
          unavailable (readyz degraded). The top-bar environment indicator
          polls /readyz for exactly that reason.
        </p>
      </div>

      {/* the full readiness document ----------------------------------- */}
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-ink">
          Readiness — GET /readyz
        </h3>
        {readinessLoading ? (
          <div aria-busy="true" className="flex flex-col gap-2">
            <div className="h-4 w-56 animate-pulse rounded bg-raised" />
            <div className="h-16 w-full animate-pulse rounded bg-raised" />
          </div>
        ) : readinessError ? (
          <div className="rounded-md border border-line bg-raised">
            <ErrorState
              error={readinessError}
              onRetry={() => setTick((value) => value + 1)}
              request={{ method: "GET", path: "/readyz" }}
            />
            {degraded503 ? (
              <p className="border-t border-line px-4 py-2 text-xs text-ink-faint">
                Degraded readiness returns HTTP 503 — the typed surface
                surfaces the failure as an error. The top-bar indicator polls
                the same route every 15 seconds and carries what the body
                exposes.
              </p>
            ) : null}
          </div>
        ) : readiness ? (
          <div
            data-testid={HEALTH_PANEL_TEST_IDS.readiness}
            className={cn(
              "flex flex-col gap-2.5 rounded-md border px-3 py-2.5",
              readinessDegraded
                ? "border-warning/60 bg-warning/5"
                : "border-line bg-raised",
            )}
          >
            <dl className="flex flex-col gap-1">
              <Row
                label="ok"
                value={
                  <span
                    className={
                      readinessDegraded ? "text-warning" : "text-positive"
                    }
                  >
                    {String(readiness.ok)}
                  </span>
                }
              />
              <Row label="service" value={readiness.service} />
              <Row label="mode" value={readiness.mode} />
              <Row label="environment" value={readiness.environment} />
            </dl>
            <div className="flex flex-col gap-1.5">
              <p className="font-mono text-2xs text-ink-faint">
                backends ({Object.keys(readiness.backends ?? {}).length})
              </p>
              <BackendRows backends={readiness.backends ?? {}} />
            </div>
            {readiness.delegated_backends &&
            Object.keys(readiness.delegated_backends).length > 0 ? (
              <div className="flex flex-col gap-1.5 border-t border-line pt-2">
                <p className="font-mono text-2xs text-ink-faint">
                  delegated_backends (
                  {Object.keys(readiness.delegated_backends).length})
                </p>
                <BackendRows backends={readiness.delegated_backends} />
              </div>
            ) : null}
            {readinessDegraded ? (
              <p className="text-xs text-ink-muted">
                The runtime reports itself NOT ready — at least one backend is
                not in the ready state. Readiness names them above.
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* liveness -------------------------------------------------------- */}
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-ink">
          Liveness — GET /healthz
        </h3>
        {livenessLoading ? (
          <div aria-busy="true" className="h-12 w-full animate-pulse rounded bg-raised" />
        ) : livenessError ? (
          <div className="rounded-md border border-line bg-raised">
            <ErrorState
              error={livenessError}
              onRetry={() => setTick((value) => value + 1)}
              request={{ method: "GET", path: "/healthz" }}
            />
          </div>
        ) : liveness ? (
          <div
            data-testid={HEALTH_PANEL_TEST_IDS.liveness}
            className="flex flex-col gap-2 rounded-md border border-line bg-raised px-3 py-2.5"
          >
            <dl className="flex flex-col gap-1">
              <Row
                label="ok"
                value={
                  <span
                    className={liveness.ok ? "text-positive" : "text-warning"}
                  >
                    {String(liveness.ok)}
                  </span>
                }
              />
              <Row label="service" value={liveness.service} />
            </dl>
            <p className="text-xs text-ink-faint">
              The liveness document carries no backend detail — by design. A
              healthy healthz says the process is up, nothing more; only
              /readyz names backends.
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
