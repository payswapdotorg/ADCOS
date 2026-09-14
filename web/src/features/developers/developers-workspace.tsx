"use client";

/**
 * DevelopersWorkspace — the developer workspace page (work order
 * deliverables #1–#5): the application identity card (instant paint
 * from the session profile, fresh truth from the page's own
 * re-fetch), the capability chips (granted + missing), the honest
 * credentials state view, and the webhook endpoints section (list /
 * register / detail / deliveries).
 *
 * Disconnected: ONLY the connect guidance — never fake application
 * data. Every request flows through the typed client from
 * useSession(); nothing here talks to the network directly.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import type { AdcosEnvelope, Application } from "@/lib/api/types";
import { useSession } from "@/lib/session";
import { registerCommand } from "@/features/search";
import { ConsoleSearchProviders } from "@/features/search/providers";
import { ensureRequestRecorder } from "@/features/requests/recorder";
import { capabilityGranted } from "./capabilities";
import { useDevelopersRead } from "./use-developers-read";
import { ConnectGuidance } from "./connect-guidance";
import { ApplicationIdentityCard } from "./application-identity-card";
import { CapabilityChips } from "./capability-chips";
import { CredentialsState } from "./credentials-state";
import { WebhookEndpointsSection } from "./webhook-endpoints-section";

export function DevelopersWorkspace() {
  const { status, application, client } = useSession();
  const connected = status === "connected";

  // the page's OWN re-fetch (so its request shows in the identity
  // card's ApiRequestPanel); the session's already-loaded profile
  // paints instantly meanwhile
  const selfRead = useDevelopersRead<AdcosEnvelope<Application>>(
    connected ? () => client.applicationSelf() : null,
    [client, connected],
  );
  const app = selfRead.data?.data ?? application;

  const canReadWebhooks = capabilityGranted("webhooks:read", app?.capabilities);
  const canWriteWebhooks = capabilityGranted(
    "webhooks:write",
    app?.capabilities,
  );

  // the register drawer's open state lives HERE so the command
  // palette action can open it (permission-aware: registered only
  // while webhooks:write is granted)
  const [registerOpen, setRegisterOpen] = useState(false);

  // the recorder wraps global fetch BEFORE any typed-client call on
  // this page. Without it, the client's doFetch getter hands the
  // UNBOUND native fetch to a method-style invocation — chromium
  // rejects that with "Illegal invocation", so connect/reads fail as
  // backend-unreachable in a REAL browser (tests stub fetch with plain
  // functions and never see it). The recorder's plain wrapper is
  // receiver-safe and captures the wire truth for the inspector.
  useEffect(() => {
    ensureRequestRecorder();
  }, []);

  useEffect(() => {
    if (!connected || canWriteWebhooks !== true) return;
    return registerCommand({
      id: "developers-register-webhook",
      title: "Register webhook endpoint",
      group: "Actions",
      keywords: ["webhook", "endpoint", "register", "events"],
      run: () => setRegisterOpen(true),
    });
  }, [connected, canWriteWebhooks]);

  const header = (
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-ink">Developers</h1>
        <p className="mt-1 text-sm text-ink-muted">
          The connected application — identity, capabilities, credential state
          and webhook endpoints. Every value renders exactly as the backend
          returns it; every request the page makes is reproducible in place.
        </p>
        {/* the area's sub-surfaces (the frozen UX: the API Explorer and
            the Request Inspector are Developers-area content) */}
        <nav aria-label="Developers area" className="mt-2 flex flex-wrap gap-4 text-sm">
          <Link
            href="/developers/explorer"
            className="font-medium text-accent hover:underline"
          >
            API Explorer →
          </Link>
          <Link
            href="/developers/requests"
            className="font-medium text-accent hover:underline"
          >
            Request inspector →
          </Link>
        </nav>
      </div>
    </header>
  );

  if (!connected) {
    return (
      <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
        <div className="flex flex-col gap-4">
          {header}
          <ConnectGuidance lead="The Developers workspace is an authenticated developer-API surface — connect an application to see its identity, capabilities and webhook endpoints." />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <div className="flex flex-col gap-4">
        {header}

        {/* the frozen-shape console search providers mount (the
            search subagent owns the implementation) */}
        <ConsoleSearchProviders />

        <div className="grid items-start gap-4 lg:grid-cols-2">
          <ApplicationIdentityCard application={application} read={selfRead} />
          {app ? (
            <CredentialsState application={app} />
          ) : (
            <div aria-busy="true" className="h-40 animate-pulse rounded-md border border-line bg-surface" />
          )}
        </div>

        {app ? (
          <CapabilityChips application={app} />
        ) : (
          <div aria-busy="true" className="h-32 animate-pulse rounded-md border border-line bg-surface" />
        )}

        <WebhookEndpointsSection
          canRead={canReadWebhooks === true}
          canWrite={canWriteWebhooks === true}
          registerOpen={registerOpen}
          onRegisterOpenChange={setRegisterOpen}
        />
      </div>
    </div>
  );
}
