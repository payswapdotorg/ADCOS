"use client";

/**
 * The runtime environment indicator — REAL readiness, never an assumption.
 *
 * Polls GET /readyz through the session's client every 15 seconds (no
 * auth; the route is a platform surface) and renders exactly what the
 * runtime reported:
 *   200 + ok       → healthy  (positive dot, `mode · environment`)
 *   200 + ok=false → degraded (warning dot; mode/environment from the body)
 *   503            → degraded (warning dot; environment from the error
 *                    envelope when present, message as detail)
 *   network error  → unreachable (danger dot, "runtime unreachable")
 *
 * NO fake values: when the runtime reports no backends, the popover says
 * so — "no durable backends (sandbox)" ONLY for sandbox mode. The details
 * popover is a plain positioned div (no extra dependency); the trigger is
 * a status region for assistive tech.
 */

import { useEffect, useState } from "react";
import { isAdcosApiError } from "@/lib/api/errors";
import type { Readiness, ReadinessBackend } from "@/lib/api/types";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

type Phase = "healthy" | "degraded" | "unreachable";

interface EnvironmentSnapshot {
  phase: Phase;
  mode: string;
  environment: string;
  backends: Record<string, ReadinessBackend> | null;
  delegatedBackends: Record<string, ReadinessBackend> | null;
  detail: string;
  checkedAt: string;
}

const POLL_INTERVAL_MS = 15_000;

function backendRows(
  backends: Record<string, ReadinessBackend>,
): [string, ReadinessBackend][] {
  return Object.entries(backends);
}

function backendSummary(backends: Record<string, ReadinessBackend>): string {
  const rows = backendRows(backends);
  if (rows.length === 0) return "";
  return rows.map(([name, backend]) => `${name}: ${backend.state} — ${backend.detail}`).join("; ");
}

export function EnvironmentIndicator() {
  const { client } = useSession();
  const [snapshot, setSnapshot] = useState<EnvironmentSnapshot | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

  useEffect(() => {
    let mounted = true;

    async function poll(): Promise<void> {
      const checkedAt = new Date().toISOString();
      let next: EnvironmentSnapshot;
      try {
        const readiness = await client.readyz();
        next = {
          phase: readiness.ok ? "healthy" : "degraded",
          mode: readiness.mode,
          environment: readiness.environment,
          backends: readiness.backends ?? {},
          delegatedBackends: readiness.delegated_backends ?? null,
          detail: readiness.ok ? "" : backendSummary(readiness.backends ?? {}),
          checkedAt,
        };
      } catch (error) {
        if (isAdcosApiError(error) && error.status === 503) {
          // degraded readiness — the body is not exposed through the typed
          // error, so surface what IS parseable (environment, message)
          next = {
            phase: "degraded",
            mode: "",
            environment: error.environment,
            backends: null,
            delegatedBackends: null,
            detail: error.message,
            checkedAt,
          };
        } else {
          next = {
            phase: "unreachable",
            mode: "",
            environment: "",
            backends: null,
            delegatedBackends: null,
            detail: isAdcosApiError(error) ? error.message : "network error",
            checkedAt,
          };
        }
      }
      if (mounted) setSnapshot(next);
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [client]);

  const phase: Phase | "checking" = snapshot?.phase ?? "checking";
  const dotTone =
    phase === "healthy"
      ? "text-positive"
      : phase === "degraded"
        ? "text-warning"
        : phase === "unreachable"
          ? "text-danger"
          : "text-ink-faint";

  const label =
    phase === "checking"
      ? "checking…"
      : phase === "unreachable"
        ? "runtime unreachable"
        : [snapshot?.mode, snapshot?.environment].filter(Boolean).join(" · ") || "degraded";

  const title =
    phase === "degraded"
      ? snapshot?.detail || "runtime reports degraded readiness"
      : phase === "unreachable"
        ? snapshot?.detail || "the ADCOS runtime could not be reached"
        : undefined;

  return (
    <div
      role="status"
      aria-label="Runtime environment"
      className="relative"
      onKeyDown={(event) => {
        if (event.key === "Escape" && detailsOpen) setDetailsOpen(false);
      }}
    >
      <button
        type="button"
        onClick={() => setDetailsOpen((open) => !open)}
        aria-expanded={detailsOpen}
        title={title}
        className="flex max-w-56 items-center gap-2 rounded px-2 py-1 font-mono text-xs text-ink-muted hover:text-ink"
      >
        <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full bg-current", dotTone)} />
        <span className="truncate">{label}</span>
      </button>

      {detailsOpen && snapshot ? (
        <div className="absolute left-0 top-full z-30 mt-1.5 w-72 rounded-md border border-line bg-overlay p-3 shadow-[var(--shadow-panel)]">
          <dl className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1 font-mono text-xs">
            <dt className="text-ink-faint">mode</dt>
            <dd className="truncate">{snapshot.mode || "—"}</dd>
            <dt className="text-ink-faint">environment</dt>
            <dd className="truncate">{snapshot.environment || "—"}</dd>
            <dt className="text-ink-faint">state</dt>
            <dd className={dotTone}>{snapshot.phase}</dd>
          </dl>

          <div className="mt-2 border-t border-line pt-2">
            {snapshot.backends === null ? (
              <p className="text-xs text-ink-faint">
                {snapshot.detail || "backend details unavailable"}
              </p>
            ) : backendRows(snapshot.backends).length === 0 ? (
              <p className="text-xs text-ink-faint">
                {snapshot.mode === "sandbox"
                  ? "no durable backends (sandbox)"
                  : "no backends reported"}
              </p>
            ) : (
              <ul className="space-y-1">
                {backendRows(snapshot.backends).map(([name, backend]) => (
                  <li key={name} className="font-mono text-xs">
                    <span className="text-ink">{name}: </span>
                    <span className={backend.state === "ready" ? "text-positive" : "text-warning"}>
                      {backend.state}
                    </span>
                    <span className="text-ink-faint"> — {backend.detail}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {snapshot.delegatedBackends && backendRows(snapshot.delegatedBackends).length > 0 ? (
            <div className="mt-2 border-t border-line pt-2">
              <p className="text-2xs uppercase tracking-wide text-ink-faint">
                delegated backends
              </p>
              <ul className="mt-1 space-y-1">
                {backendRows(snapshot.delegatedBackends).map(([name, backend]) => (
                  <li key={name} className="font-mono text-xs">
                    <span className="text-ink">{name}: </span>
                    <span className={backend.state === "ready" ? "text-positive" : "text-warning"}>
                      {backend.state}
                    </span>
                    <span className="text-ink-faint"> — {backend.detail}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <p className="mt-2 border-t border-line pt-2 font-mono text-2xs text-ink-faint">
            last checked {snapshot.checkedAt}
          </p>
        </div>
      ) : null}
    </div>
  );
}
