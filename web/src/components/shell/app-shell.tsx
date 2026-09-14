"use client";

/**
 * The app shell — the single console frame.
 *
 * Sidebar (nav rail) + right column (top bar + main region). Owns the
 * command palette's open state: the global Cmd/Ctrl+K listener toggles
 * it, the top bar trigger opens it, and the palette mount reports close.
 * On mount it registers the default navigation commands into the command
 * registry (the palette's "Navigate" group) — the same vocabulary the
 * sidebar shows, so keyboard and mouse navigation agree.
 */

import { useEffect, useState, type ReactNode } from "react";
import {
  AssuranceIcon,
  ConnectivityIcon,
  DevelopersIcon,
  EvidenceIcon,
  FulfillmentIcon,
  HomeIcon,
  NetworksIcon,
  SettingsIcon,
} from "@/components/ui";
import { CommandPaletteMount } from "@/features/search/command-palette-mount";
import { registerCommand, type CommandRecord } from "@/features/search/command-registry";
import { Sidebar } from "./sidebar";
import { TopBar } from "./top-bar";

const NAV_COMMANDS: CommandRecord[] = [
  {
    id: "nav-home",
    title: "Home",
    href: "/",
    group: "Navigate",
    keywords: ["home", "overview", "dashboard"],
    icon: <HomeIcon className="h-3.5 w-3.5" />,
  },
  {
    id: "nav-connectivity",
    title: "Connectivity",
    href: "/connectivity",
    group: "Navigate",
    keywords: ["connectivity", "contracts", "intent", "builder"],
    icon: <ConnectivityIcon className="h-3.5 w-3.5" />,
  },
  {
    id: "nav-networks",
    title: "Networks",
    href: "/networks",
    group: "Navigate",
    keywords: ["networks", "providers", "adapters", "topology"],
    icon: <NetworksIcon className="h-3.5 w-3.5" />,
  },
  {
    id: "nav-fulfillment",
    title: "Fulfillment",
    href: "/fulfillment",
    group: "Navigate",
    keywords: ["fulfillment", "execution", "plan", "replan", "failover", "leases"],
    icon: <FulfillmentIcon className="h-3.5 w-3.5" />,
  },
  {
    id: "nav-evidence",
    title: "Evidence",
    href: "/evidence",
    group: "Navigate",
    keywords: ["evidence", "provenance", "lineage"],
    icon: <EvidenceIcon className="h-3.5 w-3.5" />,
  },
  {
    id: "nav-developers",
    title: "Developers",
    href: "/developers",
    group: "Navigate",
    keywords: ["developers", "applications", "credentials", "capabilities", "api", "explorer", "requests"],
    icon: <DevelopersIcon className="h-3.5 w-3.5" />,
  },
  {
    id: "nav-assurance",
    title: "Assurance",
    href: "/assurance",
    group: "Navigate",
    keywords: ["assurance", "objectives", "latency", "availability", "capacity", "health"],
    icon: <AssuranceIcon className="h-3.5 w-3.5" />,
  },
  {
    id: "nav-settings",
    title: "Settings",
    href: "/settings",
    group: "Navigate",
    keywords: ["settings", "appearance", "theme", "connection", "environment"],
    icon: <SettingsIcon className="h-3.5 w-3.5" />,
  },
];

export function AppShell({ children }: { children: ReactNode }) {
  const [paletteOpen, setPaletteOpen] = useState(false);

  // the default navigation commands (idempotent re-registration)
  useEffect(() => {
    const unregister = NAV_COMMANDS.map((command) => registerCommand(command));
    return () => {
      unregister.forEach((fn) => fn());
    };
  }, []);

  // Cmd/Ctrl+K toggles the palette from anywhere
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="flex min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-raised focus:px-3 focus:py-1.5 focus:text-sm focus:text-ink"
      >
        Skip to content
      </a>

      <Sidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onOpenPalette={() => setPaletteOpen(true)} />
        <main id="main" className="min-w-0 flex-1">
          {children}
        </main>
      </div>

      <CommandPaletteMount open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  );
}
