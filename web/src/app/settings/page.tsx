"use client";

/**
 * Settings — real (and deliberately small): the three console-local
 * concerns that exist TODAY. A client component by necessity (theme +
 * session hooks); it exports no metadata for that reason — the root
 * layout's default title applies.
 *
 * - Appearance: the theme preference (the ONLY thing the console
 *   persists — it is a UI setting, never a secret).
 * - Connection: the live session state + connect/disconnect inline.
 * - Environment: the real readiness indicator (polls GET /readyz).
 */

import { useState } from "react";
import { ConnectivityIcon } from "@/components/ui";
import { ConnectDialog } from "@/components/shell/connect-dialog";
import { EnvironmentIndicator } from "@/components/shell/environment-indicator";
import { useTheme } from "@/lib/design/theme";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-labelledby={id}
      className="rounded-md border border-line bg-surface"
    >
      <div className="border-b border-line px-4 py-3">
        <h2 id={id} className="text-sm font-semibold">
          {title}
        </h2>
        <p className="mt-0.5 text-sm text-ink-muted">{description}</p>
      </div>
      <div className="px-4 py-4">{children}</div>
    </section>
  );
}

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { status, application, disconnect } = useSession();
  const [connectOpen, setConnectOpen] = useState(false);

  const connected = status === "connected";

  return (
    <div className="mx-auto w-full max-w-workbench space-y-4 px-gutter py-rhythm">
      <header>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Console-local settings. Everything here runs client-side against the
          real session and runtime state.
        </p>
      </header>

      <Section
        id="settings-appearance"
        title="Appearance"
        description="Dark-first workbench; the preference is stored locally (a UI setting, never a secret)."
      >
        <div role="group" aria-label="Theme" className="flex gap-2">
          {(["dark", "light"] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={theme === option}
              onClick={() => setTheme(option)}
              className={cn(
                "rounded border px-3 py-1.5 text-sm",
                theme === option
                  ? "border-accent bg-raised text-ink"
                  : "border-line text-ink-muted hover:text-ink",
              )}
            >
              {option === "dark" ? "Dark" : "Light"}
            </button>
          ))}
        </div>
      </Section>

      <Section
        id="settings-connection"
        title="Connection"
        description="The application session is validated against GET /api/2.0/application."
      >
        <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1.5 text-sm">
          <dt className="text-ink-faint">Status</dt>
          <dd className="font-mono text-xs">{status}</dd>
          {connected && application ? (
            <>
              <dt className="text-ink-faint">Application</dt>
              <dd className="truncate font-mono text-xs">{application.application_name}</dd>
              <dt className="text-ink-faint">Application ID</dt>
              <dd className="truncate font-mono text-2xs text-ink-faint">
                {application.application_id}
              </dd>
              <dt className="text-ink-faint">Valid until</dt>
              <dd className="font-mono text-xs">{application.valid_until}</dd>
            </>
          ) : null}
        </dl>
        <div className="mt-4">
          {connected ? (
            <button
              type="button"
              onClick={disconnect}
              className="rounded border border-line px-3 py-1.5 text-sm text-danger hover:bg-danger/10"
            >
              Disconnect
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setConnectOpen(true)}
              className="flex items-center gap-2 rounded border border-line px-3 py-1.5 text-sm text-ink-muted hover:text-ink"
            >
              <ConnectivityIcon className="h-3.5 w-3.5" />
              Connect application…
            </button>
          )}
        </div>
        <p className="mt-3 text-2xs text-ink-faint">
          Session is in-memory only — reloading clears it.
        </p>
        <ConnectDialog open={connectOpen} onOpenChange={setConnectOpen} />
      </Section>

      <Section
        id="settings-environment"
        title="Environment"
        description="Readiness truth from the runtime — never a local assumption."
      >
        <EnvironmentIndicator />
        <p className="mt-3 text-2xs text-ink-faint">
          Readiness polls GET /readyz every 15 seconds (unauthenticated platform
          surface). Click the indicator for backend detail.
        </p>
      </Section>
    </div>
  );
}
