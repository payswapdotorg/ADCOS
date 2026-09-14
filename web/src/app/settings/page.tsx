"use client";

/**
 * Settings — the console-local concerns (Worker 3, Part C): appearance,
 * environment & health (the full /readyz + /healthz documents with the
 * honest liveness-vs-readiness semantics), the session (application
 * summary + disconnect + credential policy), and about (the boundary
 * statement + the error workbench link). A client component by
 * necessity (theme + session + health hooks); it exports no metadata
 * for that reason — the root layout's default title applies.
 */

import { useEffect } from "react";
import { ensureRequestRecorder } from "@/features/requests/recorder";
import { ConsoleSearchProviders } from "@/features/search/providers";
import { registerCommand } from "@/features/search";
import {
  AboutPanel,
  AppearancePanel,
  HealthPanel,
  Section,
  SessionPanel,
} from "@/features/settings";

export default function SettingsPage() {
  // capture-eligible requests + the workbench palette entry, from mount on
  useEffect(() => {
    ensureRequestRecorder();
    const unregister = registerCommand({
      id: "go-error-workbench",
      title: "Error workbench",
      group: "Navigate",
      href: "/settings/errors",
    });
    return unregister;
  }, []);

  return (
    <div className="mx-auto w-full max-w-workbench space-y-4 px-gutter py-rhythm">
      <ConsoleSearchProviders />
      <header>
        <h1 className="text-xl font-semibold text-ink">Settings</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Console-local settings. Everything here runs client-side against the
          real session and runtime state — the backend owns all truth, this
          page owns no state of its own.
        </p>
      </header>

      <Section
        id="settings-appearance"
        title="Appearance"
        description="Dark-first workbench; the preference is stored locally (a UI setting, never a secret)."
      >
        <AppearancePanel />
      </Section>

      <Section
        id="settings-health"
        title="Environment & health"
        description="The full readiness document and liveness, read live from the runtime — never a local assumption."
      >
        <HealthPanel />
      </Section>

      <Section
        id="settings-session"
        title="Session"
        description="The connected application, validated against GET /api/2.0/application."
      >
        <SessionPanel />
      </Section>

      <Section
        id="settings-about"
        title="About"
        description="What this console is — and what it deliberately is not."
      >
        <AboutPanel />
      </Section>
    </div>
  );
}
